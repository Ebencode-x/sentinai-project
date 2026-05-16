export default function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="border border-warn/40 bg-warn/5 text-warn text-xs px-4 py-3 rounded-sm tracking-wide">
      ▲ {message}
    </div>
  );
}
