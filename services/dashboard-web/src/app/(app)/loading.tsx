import { Skeleton } from "@hukuk/ui";

export default function AppLoading() {
    return (
        <main className="grid grid-cols-1 gap-6 p-4 md:p-6 lg:p-8">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-36" />
        </main>
    );
}
