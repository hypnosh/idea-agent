"""Reddit pain points -> validated SaaS ideas, using Gemini.
Usage: python agent.py smallbusiness [--out ideas.json]
"""
import json, os, re, sys, time
from datetime import datetime, timezone
import praw
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = os.environ["GEMINI_MODEL"]
KW = re.compile(r"frustrat|alternative to|wish there|anyone know|too expensive|hate|looking for", re.I)

SYSTEM_PROMPT = """You are a market research analyst, not an idea generator. You turn real user complaints from Reddit into validated SaaS opportunities.
INPUT: threads as JSON {thread_url, subreddit, title, body, score, num_comments, date, top_comments[]}
RULES
1. Every idea must cite at least 3 distinct source threads. Discard themes with fewer.
2. Never invent competitors, prices or quotes. Use only what is in the input. If unknown, use null.
3. Group similar complaints into themes before proposing anything.
4. Per theme: target user, core problem, tools mentioned, what users still dislike, the gap, monetization hints.
5. Count, don't estimate. frequency = distinct threads; wtp_mentions = comments mentioning price, "I'd pay" or budget; reach = total score + num_comments; recency_pct_30d = share of threads from the last 30 days.
6. intensity 1-5 from language (1 mild annoyance, 5 angry/blocked/losing money).
7. Prefer repeated complaints and weak competitors over novel but unproven ideas.
8. key_quote under 15 words, copied from the input.
9. Output ONLY valid JSON matching the schema."""

S, SN, I = {"type": "string"}, {"type": ["string", "null"]}, {"type": "integer"}
def obj(props): return {"type": "object", "properties": props, "required": list(props)}
IDEAS_SCHEMA = obj({"ideas": {"type": "array", "items": obj({
    "id": S, "title": S, "problem": S, "target_user": S, "product_angle": S,
    "competitors": {"type": "array", "items": obj({"name": S, "pricing": SN, "user_complaints": {"type": "array", "items": S}})},
    "gap": S,
    "monetization": obj({"model": {"type": "string", "enum": ["subscription", "usage", "one-time", "marketplace", "other"]}, "price_hint": SN, "evidence": S}),
    "metrics": obj({"frequency": I, "reach": I, "intensity": {"type": "integer", "minimum": 1, "maximum": 5},
                    "recency_pct_30d": I, "wtp_mentions": I, "competitor_count": I, "gap_strength": I}),
    "source_threads": {"type": "array", "minItems": 3, "items": obj({"url": S, "title": S, "score": I, "num_comments": I, "key_quote": S})},
    "risks": {"type": "array", "items": S},
    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
})}})

def step(msg): print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr)

def parse_or_repair(raw: str, tries: int = 2):
    for i in range(tries + 1):
        try:
            return json.loads(re.sub(r"```json|```", "", raw).strip())
        except json.JSONDecodeError as e:
            if i == tries: raise
            raw = client.models.generate_content(
                model=MODEL,
                contents=f"The following output is invalid JSON. Fix syntax only. Do not change content. Return only valid JSON.\n<broken>{raw}</broken>\n<error>{e}</error>",
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            ).text or ""

def collect(sub: str):
    reddit = praw.Reddit(client_id=os.environ["REDDIT_ID"], client_secret=os.environ["REDDIT_SECRET"],
                         username=os.environ["REDDIT_USER"], password=os.environ["REDDIT_PASS"],
                         user_agent="idea-agent/1.0")
    out = []
    for p in reddit.subreddit(sub).top(time_filter="year", limit=100):
        if p.num_comments < 10 or not KW.search(f"{p.title} {p.selftext}"): continue
        p.comment_sort = "top"; p.comments.replace_more(limit=0)
        out.append({
            "thread_url": f"https://reddit.com{p.permalink}", "subreddit": sub, "title": p.title,
            "body": p.selftext[:1500], "score": p.score, "num_comments": p.num_comments,
            "date": datetime.fromtimestamp(p.created_utc, timezone.utc).isoformat(),
            "top_comments": [c.body for c in list(p.comments)[:15]],
        })
        if len(out) == 25: break
    return out

def analyze(threads):
    res = client.models.generate_content(
        model=MODEL, contents=json.dumps(threads),
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, response_mime_type="application/json",
                                           response_json_schema=IDEAS_SCHEMA, temperature=0.2))
    return parse_or_repair(res.text or "")["ideas"]

def validate(idea):
    try:
        res = client.models.generate_content(
            model=MODEL,
            contents=f'Find real competitors, pricing and user complaints for: "{idea["title"]}" ({idea["problem"]}).\n'
                     'Return ONLY JSON: {"competitors":[{"name":"","pricing":null,"user_complaints":[]}]}. Use null if unknown. Never invent.',
            config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]))
        idea["competitors"] = parse_or_repair(res.text or "").get("competitors", idea["competitors"])
        idea["metrics"]["competitor_count"] = len(idea["competitors"])
        meta = res.candidates[0].grounding_metadata
        idea["sources_web"] = [{"title": c.web.title, "url": c.web.uri} for c in (meta.grounding_chunks or [])] if meta else []
    except Exception as e:
        idea["validation_failed"] = str(e)
    return idea

def score(m):
    n = lambda v, cap: min(v / cap, 1)
    return round(100 * (0.25 * n(m["frequency"], 20) + 0.15 * n(m["reach"], 5000) + 0.20 * n(m["intensity"], 5)
                        + 0.15 * n(m["wtp_mentions"], 10) + 0.10 * n(m["recency_pct_30d"], 100) + 0.15 * n(m["gap_strength"], 10)))

def run(sub: str):
    step("Scraping Reddit threads"); threads = collect(sub)
    step(f"Analyzing {len(threads)} threads"); ideas = analyze(threads)
    step(f"Validating {len(ideas)} ideas"); ideas = [validate(i) for i in ideas]
    step("Scoring ideas")
    for i in ideas: i["opportunity_score"] = score(i["metrics"])
    ideas.sort(key=lambda i: i["opportunity_score"], reverse=True)
    return {"ideas": ideas, "meta": {"subreddit": sub, "threads_analyzed": len(threads),
                                     "generated_at": datetime.now(timezone.utc).isoformat()}}

if __name__ == "__main__":
    result = run(sys.argv[1].removeprefix("r/"))
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "ideas.json"
    json.dump(result, open(out, "w"), indent=2)
    for i in result["ideas"]:
        print(f'{i["opportunity_score"]:>3}  {i["title"]}')
    print(f"\nSaved to {out}", file=sys.stderr)