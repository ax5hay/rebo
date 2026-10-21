// The ReBo mark: an R built from the bot's own material. The stem is a tall data bar, the bowl is a lens
// (reading your question), the leg is a short report bar. Same drawing as public/logo.svg and the
// banner in docs/images; colours stay fixed in both themes.
export function Mark({ size = 28 }: { size?: number }) {
  return (
    <svg className="mark" width={size} height={size} viewBox="0 0 64 64" aria-hidden>
      <rect width="64" height="64" rx="16" fill="#0d1b24" />
      <circle cx="30" cy="24" r="10" fill="none" stroke="#3fd0a6" strokeWidth="6.5" />
      <rect x="14" y="11" width="9" height="40" rx="4.5" fill="#f4f7f8" />
      <rect x="33" y="35" width="9.5" height="16" rx="4.75" fill="#e6a93c" />
    </svg>
  );
}

export function Wordmark({ size = 28 }: { size?: number }) {
  return <span className="wordmark"><Mark size={size} /><span>ReBo</span></span>;
}
