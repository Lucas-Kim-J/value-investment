import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Shared markdown renderer (reports, analyses, /doc content) with the design system. */
export function Markdown({ children, className = "md-render" }: { children: string; className?: string }) {
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children || ""}</ReactMarkdown>
    </div>
  );
}
