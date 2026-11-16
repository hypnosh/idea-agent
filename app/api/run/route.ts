import { collect } from "@/lib/reddit";
import { analyze } from "@/lib/analyze";
import { validate } from "@/lib/validate";
import { score } from "@/lib/score";

export async function POST(req: Request) {
  const { subreddit } = await req.json();
  const enc = new TextEncoder();
  const stream = new ReadableStream({
    async start(ctrl) {
      const send = (o: any) => ctrl.enqueue(enc.encode(JSON.stringify(o) + "\n"));
      try {
        send({ stage: "Scraping Reddit threads" });
        const threads = await collect(subreddit);
        send({ stage: "Grouping complaints and analyzing" });
        let ideas = await analyze(threads);
        send({ stage: "Validating competitors" });
        ideas = await Promise.all(ideas.map(validate));
        send({ stage: "Scoring ideas" });
        ideas.forEach((i: any) => (i.opportunity_score = score(i.metrics)));
        ideas.sort((a: any, b: any) => b.opportunity_score - a.opportunity_score);
        send({ done: true, ideas });
      } catch (e: any) { send({ error: e.message }); }
      ctrl.close();
    },
  });
  return new Response(stream, { headers: { "Content-Type": "application/x-ndjson" } });
}