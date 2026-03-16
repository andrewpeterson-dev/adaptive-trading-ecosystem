export default function EditStrategyRoute({ params }: { params: { id: string } }) {
  return <div className="app-page p-8 text-center text-muted-foreground">Editing strategy {params.id}...</div>;
}
