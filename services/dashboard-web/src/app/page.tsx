import { Card, CardContent, CardHeader, CardTitle, Logo } from "@hukuk/ui";
import { useTranslations } from "next-intl";

export default function Home() {
    const t = useTranslations();
    return (
        <main className="flex min-h-screen items-center justify-center p-6">
            <Card className="w-full max-w-sm">
                <CardHeader className="items-center justify-items-center gap-3 text-primary">
                    <Logo label={t("brand.logoLabel")} className="size-10" />
                    <CardTitle className="font-serif text-xl text-ink">{t("brand.name")}</CardTitle>
                </CardHeader>
                <CardContent className="text-center text-sm text-muted-foreground">
                    {t("foundation.ready")}
                </CardContent>
            </Card>
        </main>
    );
}
