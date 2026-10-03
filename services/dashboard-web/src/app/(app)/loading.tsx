import { Skeleton } from "@hukuk/ui";

export default function AppLoading() {
    return (
        <main className="grid gap-6 p-8">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-36" />
        </main>
    );
}
