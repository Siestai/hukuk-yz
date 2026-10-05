import { AppNav, type AppNavProps } from "./app-nav";
import { Brand } from "./brand";

/** The fixed navigation column of wide screens (`lg` and up); narrower screens use the mobile bar. */
export function SideNav(props: AppNavProps) {
    return (
        <aside className="hidden w-64 shrink-0 flex-col border-r border-line bg-surface lg:flex">
            <div className="p-5">
                <Brand />
            </div>
            <AppNav {...props} />
        </aside>
    );
}
