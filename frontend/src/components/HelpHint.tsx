import { clsx } from 'clsx';

interface Props {
  term: string;
  meaning: string;
  className?: string;
}

export default function HelpHint({ term, meaning, className }: Props) {
  return (
    <span className={clsx('inline-flex items-center gap-1', className)}>
      <span>{term}</span>
      <span
        className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-gray-200 text-[10px] font-bold leading-none text-gray-700 cursor-help"
        title={meaning}
        aria-label={`${term}: ${meaning}`}
      >
        ?
      </span>
    </span>
  );
}
