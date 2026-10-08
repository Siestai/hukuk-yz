import { Skeleton } from "@hukuk/ui";

export default function StatuteLoading() {
    return (
        <main className="grid grid-cols-1 gap-6 p-4 md:p-6 lg:p-8">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-9 w-2/3" />
            <Skeleton className="h-32" />
            <Skeleton className="h-96" />
        </main>
    );
}
