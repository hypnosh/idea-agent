export async function validate(idea: any) {
  const res = await ai.models.generateContent({
    model: MODEL,
    contents: `Find real competitors, pricing and user complaints for: "${idea.title}" (${idea.problem}).
Return ONLY JSON: {"competitors":[{"name":"","pricing":null,"user_complaints":[]}]}. Use null if unknown. Never invent.`,
    config: { tools: [{ googleSearch: {} }] },
  });
  const v = await parseOrRepair(res.text ?? "");
  idea.competitors = v.competitors;
  idea.metrics.competitor_count = v.competitors.length;
  idea.sources_web = res.candidates?.[0]?.groundingMetadata?.groundingChunks ?? [];
  return idea;
}