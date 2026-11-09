export function Logo({ className }: { className?: string }) {
  // A play triangle whose right edge becomes a speech-bubble tail: "talk to the video".
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden fill="none">
      <rect x="1" y="1" width="30" height="30" rx="9" className="fill-fg" />
      <path d="M12 9.5v13l10-6.5-10-6.5Z" className="fill-bg" />
      <circle cx="24.5" cy="24.5" r="3.5" className="fill-accent" />
    </svg>
  );
}
