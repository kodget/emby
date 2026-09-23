/** Shared shapes for content returned by the curriculum and quiz APIs. */
export type ReaderBlock =
  | { type: "h1"; text: string }
  | { type: "h2"; text: string }
  | { type: "p"; text: string }
  | { type: "figure"; src: string; caption: string }
  | { type: "list"; items: string[] }
  | {
      type: "callout";
      variant: "clinical" | "highyield" | "mnemonic";
      title: string;
      body: string;
    }
  | { type: "slide"; src: string; pageNumber: number };

export type MCQ = {
  id: string;
  question: string;
  options: string[];
  correct: number;
  explanation: string;
  topic: string;
};
