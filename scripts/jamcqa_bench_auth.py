#!/usr/bin/env python3
"""JamC-QA v1.0 benchmark for OpenAI-compatible API (llama-server)

jcq_bench.py (JCommonsenseQA driver) の派生版。RUNBOOK軸2の指示により、
新規実装ではなくJCQドライバの構造を移送してJamC-QA用に改造したもの。
"""

import json
import time
import argparse
import httpx
from datasets import load_dataset

def build_prompt(question, choices):
    lines = [f"質問: {question}"]
    for i, c in enumerate(choices):
        lines.append(f"{i}: {c}")
    lines.append("回答（番号のみ）:")
    return "\n".join(lines)

def build_messages(question, choices, few_shot):
    messages = [
        {"role": "system", "content": "あなたは日本に関する知識問題に答えるアシスタントです。選択肢の番号のみを回答してください。"}
    ]
    for ex in few_shot:
        messages.append({"role": "user", "content": build_prompt(ex["question"], ex["choices"])})
        messages.append({"role": "assistant", "content": str(ex["answer"])})
    messages.append({"role": "user", "content": build_prompt(question, choices)})
    return messages

def extract_answer(text):
    if not text:
        return -1
    text = text.strip()
    for ch in text:
        if ch in "0123":
            return int(ch)
    return -1

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8080/v1/chat/completions")
    parser.add_argument("--model", default="gemma4")
    parser.add_argument("--max-tokens", type=int, default=8)
    parser.add_argument("--output", default="jamcqa_results.json")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--num-shots", type=int, default=3)
    parser.add_argument("--reasoning-effort", default="none",
                         help="top-level reasoning_effort field (some models: none/low/medium/xhigh). Empty string to omit.")
    args = parser.parse_args()

    dev = list(load_dataset("sbintuitions/JamC-QA", "v1.0", split="dev"))
    few_shot = [
        {
            "question": ex["question"],
            "choices": [ex[f"choice{j}"] for j in range(4)],
            "answer": ex["answer_index"],
        }
        for ex in dev[: args.num_shots]
    ]

    ds = load_dataset("sbintuitions/JamC-QA", "v1.0", split="test")
    items = list(ds)
    if args.limit > 0:
        items = items[: args.limit]

    results = []
    correct = 0
    total_latency = 0.0
    total_tps_list = []

    # guard gate 集計 (INBOX_005 §3-4。リトライで条件をばらつかせず、異常は異常として記録する)
    n_empty_content = 0
    n_finish_length = 0
    n_thinking_contam = 0
    n_reasoning_nonempty = 0
    THINK_MARKERS = ("<think>", "</think>", "<unused49>")

    import os; client = httpx.Client(timeout=600.0, headers={"Authorization": "Bearer " + os.environ.get("STRATA_KEY", "")})

    for i, item in enumerate(items):
        choices = [item[f"choice{j}"] for j in range(4)]
        messages = build_messages(item["question"], choices, few_shot)

        t0 = time.time()
        try:
            req_body = {
                "model": args.model,
                "messages": messages,
                "max_tokens": args.max_tokens,
                "temperature": 0.0,
            }
            if args.reasoning_effort:
                # Some models: reasoning_effort must be a TOP-LEVEL field (not under
                # chat_template_kwargs) for "none" to bypass the Jinja template's
                # xhigh/medium/low-only validation (KNOWN_ISSUES.md, verified in round6 prep).
                req_body["reasoning_effort"] = args.reasoning_effort
            resp = client.post(args.api_url, json=req_body)
            data = resp.json()

            if "choices" not in data:
                print(f"[{i+1}] API error: {json.dumps(data, ensure_ascii=False)[:200]}")
                results.append({"qid": item["qid"], "category": item["category"], "question": item["question"],
                                "gold": item["answer_index"], "pred": -1, "correct": False,
                                "response": str(data), "latency": 0})
                continue

            msg = data["choices"][0]["message"]
            content = msg.get("content", "")
            reasoning = msg.get("reasoning_content", "")
            finish = data["choices"][0].get("finish_reason", "")

            # guard gate 集計のみ行い、リトライはしない (INBOX_005 §3-4: リトライは問題ごとに
            # 計算量をばらつかせるため禁止。異常は異常のまま記録し、ラン全体をguard_gateで判定する)
            if not content.strip():
                n_empty_content += 1
            if finish == "length":
                n_finish_length += 1
            if any(m in content for m in THINK_MARKERS):
                n_thinking_contam += 1
            if reasoning.strip():
                n_reasoning_nonempty += 1

            timings = data.get("timings", {})
            pred_tps = timings.get("predicted_per_second", 0)
            if pred_tps > 0:
                total_tps_list.append(pred_tps)

        except Exception as e:
            print(f"[{i+1}] Error: {e}")
            results.append({"qid": item["qid"], "category": item["category"], "question": item["question"],
                            "gold": item["answer_index"], "pred": -1, "correct": False,
                            "response": str(e), "latency": 0})
            continue

        latency = time.time() - t0
        total_latency += latency

        pred = extract_answer(content)
        gold = item["answer_index"]
        is_correct = pred == gold

        if is_correct:
            correct += 1

        results.append({
            "qid": item["qid"],
            "category": item["category"],
            "difficulty": item.get("difficulty"),
            "question": item["question"],
            "gold": gold,
            "pred": pred,
            "correct": is_correct,
            "response": content,
            "reasoning": reasoning[:200] if reasoning else "",
            "latency": round(latency, 3),
            "tok_s": round(pred_tps, 1),
        })

        acc = correct / (i + 1) * 100
        think_flag = "T" if reasoning else ""
        print(f"[{i+1}/{len(items)}] acc={acc:.1f}% lat={latency:.2f}s tps={pred_tps:.1f} pred={pred} gold={gold} {'✓' if is_correct else '✗'} {think_flag}")

    avg_latency = total_latency / len(items) if items else 0
    avg_tps = sum(total_tps_list) / len(total_tps_list) if total_tps_list else 0

    # カテゴリ別集計 (RUNBOOKの8カテゴリ横断評価のため)
    by_category = {}
    for r in results:
        cat = r.get("category", "unknown")
        by_category.setdefault(cat, {"total": 0, "correct": 0})
        by_category[cat]["total"] += 1
        if r["correct"]:
            by_category[cat]["correct"] += 1
    for cat, v in by_category.items():
        v["accuracy"] = round(v["correct"] / v["total"] * 100, 2) if v["total"] else 0

    guard_pass = (n_empty_content == 0 and n_finish_length == 0
                  and n_thinking_contam == 0 and n_reasoning_nonempty == 0)
    guard_gate = {
        "pass": guard_pass,
        "empty_content_count": n_empty_content,
        "finish_length_count": n_finish_length,
        "thinking_contamination_count": n_thinking_contam,
        "reasoning_nonempty_count": n_reasoning_nonempty,
    }

    summary = {
        "dataset": "sbintuitions/JamC-QA v1.0 (test split)",
        "num_shots": args.num_shots,
        "reasoning_effort": args.reasoning_effort,
        "model": args.model,
        "total": len(items),
        "correct": correct,
        "accuracy": round(correct / len(items) * 100, 2),
        "avg_latency": round(avg_latency, 3),
        "avg_tok_s": round(avg_tps, 1),
        "guard_gate": guard_gate,
        "by_category": by_category,
        "results": results,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n=== Results ===")
    print(f"Model: {args.model}")
    print(f"Accuracy: {correct}/{len(items)} ({summary['accuracy']}%)")
    print(f"Avg latency: {avg_latency:.3f}s")
    print(f"Avg tok/s: {avg_tps:.1f}")
    print(f"\n=== Guard Gate (INBOX_005 §3-4) ===")
    print(f"empty_content={n_empty_content}  finish_length={n_finish_length}  "
          f"thinking_contamination={n_thinking_contam}  reasoning_nonempty={n_reasoning_nonempty}")
    print(f"GUARD GATE: {'PASS' if guard_pass else 'FAIL — この結果は成果物として使用不可、原因調査すること'}")
    print(f"Saved: {args.output}")

if __name__ == "__main__":
    main()
