export default function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-muted">
      <div className="text-4xl mb-4 opacity-20">◈</div>
      <p className="text-xs tracking-widest">{message}</p>
    </div>
  );
}
