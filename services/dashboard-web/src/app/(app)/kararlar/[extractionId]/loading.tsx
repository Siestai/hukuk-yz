import { Skeleton } from "@hukuk/ui";

export default function DecisionLoading() {
    return (
        <main className="grid gap-6 p-8">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-9 w-2/3" />
            <div className="grid gap-6 lg:grid-cols-2">
                <div className="grid gap-4">
                    <Skeleton className="h-96" />
                    <Skeleton className="h-48" />
                </div>
                <Skeleton className="h-screen" />
            </div>
        </main>
    );
}
