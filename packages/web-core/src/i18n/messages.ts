import shared from "../../messages/tr.json";

/** The texts of an app plus the shared ones (errors, login form). */
export function withSharedMessages<T extends object>(app: T) {
    return { ...shared, ...app };
}
