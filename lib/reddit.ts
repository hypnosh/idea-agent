const KW = /frustrat|alternative to|wish there|anyone know|too expensive|hate|looking for/i;
const H = { Authorization: `Bearer ${process.env.REDDIT_TOKEN}`, "User-Agent": "idea-agent/1.0" };

export async function collect(sub: string) {
  const r = await fetch(`https://oauth.reddit.com/r/${sub}/top?t=quarter&limit=50`, { headers: H });
  const posts = (await r.json()).data.children.map((c: any) => c.data)
    .filter((p: any) => p.num_comments >= 10 && KW.test(p.title + " " + p.selftext))
    .slice(0, 25);

  return Promise.all(posts.map(async (p: any) => {
    const c = await fetch(`https://oauth.reddit.com/comments/${p.id}?limit=15&sort=top`, { headers: H });
    const top = (await c.json())[1].data.children
      .filter((x: any) => x.kind === "t1").slice(0, 15).map((x: any) => x.data.body);
    return {
      thread_url: "https://reddit.com" + p.permalink, subreddit: sub, title: p.title,
      body: p.selftext.slice(0, 1500), score: p.score, num_comments: p.num_comments,
      date: new Date(p.created_utc * 1000).toISOString(), top_comments: top,
    };
  }));
}