"use client";

import messages from "../../messages/tr.json";

// Replaces the root layout, so there are no providers: the Turkish messages are imported directly.
export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
    return (
        <html lang="tr">
            <body>
                <main role="alert">
                    <h1>{messages.errorPage.title}</h1>
                    <p>{messages.errors.generic}</p>
                    <button type="button" onClick={reset}>
                        {messages.errorPage.retry}
                    </button>
                </main>
            </body>
        </html>
    );
}
