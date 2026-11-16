import { ai, MODEL } from "./gemini";
import { parseOrRepair } from "./json";
import { SYSTEM_PROMPT, IDEAS_SCHEMA } from "./prompt"; // paste the prompt and schema from earlier

export async function analyze(threads: any[]) {
  const res = await ai.models.generateContent({
    model: MODEL,
    contents: JSON.stringify(threads),
    config: {
      systemInstruction: SYSTEM_PROMPT,
      responseMimeType: "application/json",
      responseJsonSchema: IDEAS_SCHEMA,
      temperature: 0.2,
    },
  });
  return (await parseOrRepair(res.text ?? "")).ideas;
}