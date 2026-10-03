import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { readFields } from "@/lib/decision-fields";
import { renderWithIntl } from "@/test/intl";
import { ActionBar } from "./action-bar";
import { FieldsPanel } from "./fields-panel";
import { NAVIGATION_TIMEOUT_MS, ReviewProvider } from "./review-session";

const push = vi.hoisted(() => vi.fn());
const refresh = vi.hoisted(() => vi.fn());
const GET = vi.hoisted(() => vi.fn());
const POST = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh }) }));
vi.mock("@/lib/api/client", () => ({ createApiClient: () => ({ GET, POST }) }));

const ID = "3f0c9b1e-8a52-4a53-9d7c-2f4f6b1d9a10";
const NEXT = "7a1d5c2e-1b34-4c8e-9f60-0d2b8e4a7c11";
const fields = readFields({
    court: "yargitay",
    court_level: "daire",
    chamber: "9. HD",
    esas_no: "2019/1234",
    karar_no: "2021/567",
    decision_date: "2021-03-05",
    related_articles: [
        { statute: 4857, label: "4857 SK", articles: ["18"], raw: "4857 S. İşK/18" },
    ],
    outcome: "onama",
    keywords: ["fesih"],
});
const queue = { band: "low", sort: "score_asc", page: 1 } as const;
const done = { data: { review_id: "r1", decision_id: "d1", source_status: "approved" } };

function setup({ canAct = true, pos = 4 }: { canAct?: boolean; pos?: number } = {}) {
    return renderWithIntl(
        <ReviewProvider extractionId={ID} queue={queue} pos={pos} canAct={canAct}>
            <ActionBar />
            <FieldsPanel fields={fields} />
        </ReviewProvider>,
    );
}

const OTHER = ["p0", "p1", "p2", "p3"];

/** The queue of the API: it answers list calls by offset and limit, and an action takes the record out. */
function serveQueue(ids: string[]) {
    let queued = ids;
    GET.mockImplementation(
        async (_path: string, init: { params: { query: { offset: number; limit: number } } }) => {
            const { offset, limit } = init.params.query;
            return {
                data: {
                    total: queued.length,
                    items: queued
                        .slice(offset, offset + limit)
                        .map((id) => ({ extraction_id: id })),
                },
            };
        },
    );
    POST.mockImplementation(async () => {
        queued = queued.filter((id) => id !== ID);
        return done;
    });
}

const offsets = () =>
    GET.mock.calls.map(
        (call) => (call[1] as { params: { query: { offset: number } } }).params.query.offset,
    );

beforeEach(() => {
    vi.clearAllMocks();
    serveQueue([...OTHER, ID, NEXT, "p6"]);
});

const posted = () => (POST.mock.calls[0] as [string, { body: unknown }])[1].body;

describe("ReviewActions", () => {
    it("renders no actions for a record that is not in the queue", () => {
        setup({ canAct: false });
        expect(screen.queryByRole("button", { name: /Onayla/ })).not.toBeInTheDocument();
        fireEvent.keyDown(document.body, { key: "a" });
        expect(POST).not.toHaveBeenCalled();
    });

    it("shows each shortcut next to its action and the navigation shortcuts in a legend", () => {
        setup();
        expect(screen.getByRole("button", { name: /^Onayla A$/ })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /^Düzelt ve onayla E$/ })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /^Reddet R$/ })).toBeInTheDocument();
        expect(screen.getByText("Sonraki kayıt")).toHaveTextContent("J");
        expect(screen.getByText("Önceki kayıt")).toHaveTextContent("K");
    });

    it("approves at once, without a dialog, and moves to the record now at the same position", async () => {
        setup();
        await userEvent.click(screen.getByRole("button", { name: /^Onayla/ }));
        await waitFor(() => expect(push).toHaveBeenCalled());
        expect(posted()).toEqual({ action: "approve" });
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
        expect(offsets()).toEqual([4, 4]);
        expect(GET.mock.calls[0]![1]).toMatchObject({
            params: { query: { band: "low", limit: 1, offset: 4 } },
        });
        expect(push).toHaveBeenCalledWith(`/kararlar/${NEXT}?band=low&pos=4&flash=approved`);
        // The counts are refreshed by the screen that shows the notice, not in this transition.
        expect(refresh).not.toHaveBeenCalled();
    });

    describe("the position of the record", () => {
        const approve = () => userEvent.click(screen.getByRole("button", { name: /^Onayla/ }));

        it("is verified against the queue before acting; a wrong one is looked up in the page window", async () => {
            serveQueue(["a", "b", ID, NEXT]);
            setup({ pos: 0 });
            await approve();
            await waitFor(() => expect(push).toHaveBeenCalled());
            expect(push).toHaveBeenCalledWith(`/kararlar/${NEXT}?band=low&pos=2&flash=approved`);
            expect(offsets().slice(0, 2)).toEqual([0, 0]);
        });

        it("goes back to the list, not to a finished queue, when the record is not in the queue", async () => {
            serveQueue(["a", "b"]);
            setup({ pos: 7 });
            await approve();
            await waitFor(() => expect(push).toHaveBeenCalledWith("/?band=low&flash=approved"));
        });

        it("goes back to the list when the lookups fail, and still posts the action", async () => {
            GET.mockRejectedValue(new TypeError("fetch failed"));
            setup();
            await approve();
            await waitFor(() => expect(push).toHaveBeenCalledWith("/?band=low&flash=approved"));
            expect(POST).toHaveBeenCalledTimes(1);
        });

        it("does not call a queue finished when only the lookup of the next record fails", async () => {
            const lookup = GET.getMockImplementation()!;
            GET.mockImplementation(async (...args: unknown[]) => {
                if (POST.mock.calls.length > 0) throw new TypeError("fetch failed");
                return lookup(...args);
            });
            setup();
            await approve();
            await waitFor(() => expect(push).toHaveBeenCalledWith("/?band=low&flash=approved"));
        });

        it("starts over from the top of the queue when the record was the last one", async () => {
            serveQueue(["a", "b", ID]);
            setup({ pos: 2 });
            await approve();
            await waitFor(() =>
                expect(push).toHaveBeenCalledWith("/kararlar/a?band=low&pos=0&flash=approved"),
            );
            expect(offsets()).toEqual([2, 2, 0]);
        });

        it("ends the queue only when offset 0 returns nothing", async () => {
            serveQueue([ID]);
            setup({ pos: 0 });
            await approve();
            await waitFor(() =>
                expect(push).toHaveBeenCalledWith("/?band=low&flash=approved&done=1"),
            );
        });

        it("is not trusted for J and K either: J past the end stays, K on an unknown record leaves for the list", async () => {
            serveQueue([ID]);
            const { unmount } = setup({ pos: 0 });
            fireEvent.keyDown(document.body, { key: "j" });
            expect(await screen.findByText("Kuyrukta sonraki kayıt yok.")).toBeInTheDocument();
            expect(push).not.toHaveBeenCalled();
            unmount();
            serveQueue(["a"]);
            setup({ pos: 3 });
            fireEvent.keyDown(document.body, { key: "k" });
            await waitFor(() => expect(push).toHaveBeenCalledWith("/?band=low"));
        });
    });

    describe("when the screen does not change", () => {
        beforeEach(() => vi.useFakeTimers());
        afterEach(() => vi.useRealTimers());

        it("gives the actions back with a way to the queue after the timeout", async () => {
            setup();
            fireEvent.click(screen.getByRole("button", { name: /^Onayla/ }));
            await act(() => vi.advanceTimersByTimeAsync(NAVIGATION_TIMEOUT_MS - 1000));
            expect(push).toHaveBeenCalled();
            expect(screen.queryByRole("alert")).not.toBeInTheDocument();
            expect(screen.getByRole("button", { name: /İşleniyor/ })).toBeDisabled();
            await act(() => vi.advanceTimersByTimeAsync(1000));
            const alert = screen.getByRole("alert");
            expect(within(alert).getByRole("link", { name: "Kuyruğa dön" })).toHaveAttribute(
                "href",
                "/?band=low",
            );
            expect(screen.getByRole("button", { name: /^Onayla/ })).toBeEnabled();
        });

        it("does the same when the navigation throws", async () => {
            push.mockImplementationOnce(() => {
                throw new Error("navigation failed");
            });
            setup();
            fireEvent.click(screen.getByRole("button", { name: /^Onayla/ }));
            await act(() => vi.advanceTimersByTimeAsync(0));
            expect(screen.getByRole("link", { name: "Kuyruğa dön" })).toBeInTheDocument();
            expect(screen.getByRole("button", { name: /^Onayla/ })).toBeEnabled();
        });

        it("stops waiting when the screen is replaced", async () => {
            const { unmount } = setup();
            fireEvent.click(screen.getByRole("button", { name: /^Onayla/ }));
            await act(() => vi.advanceTimersByTimeAsync(0));
            unmount();
            expect(vi.getTimerCount()).toBe(0);
        });
    });

    it("disables every action while a request runs and sends only one", async () => {
        let finish: (value: unknown) => void = () => {};
        POST.mockReset();
        POST.mockReturnValue(new Promise((resolve) => (finish = resolve)));
        setup();
        await userEvent.click(screen.getByRole("button", { name: /^Onayla/ }));
        const bar = screen.getByRole("region", { name: "İnceleme işlemleri" });
        await waitFor(() =>
            expect(within(bar).getByRole("button", { name: /İşleniyor/ })).toBeDisabled(),
        );
        for (const button of within(bar).getAllByRole("button")) expect(button).toBeDisabled();
        fireEvent.keyDown(document.body, { key: "a" });
        fireEvent.keyDown(document.body, { key: "j" });
        finish(done);
        await waitFor(() => expect(push).toHaveBeenCalled());
        expect(POST).toHaveBeenCalledTimes(1);
    });

    it("runs the shortcuts: A approves, J and K move without acting", async () => {
        setup();
        fireEvent.keyDown(document.body, { key: "j" });
        await waitFor(() => expect(push).toHaveBeenCalledWith(`/kararlar/${NEXT}?band=low&pos=5`));
        expect(POST).not.toHaveBeenCalled();
        expect(offsets()).toEqual([4, 5]);
    });

    it("K at the first position says there is no previous record", async () => {
        serveQueue([ID, NEXT]);
        setup({ pos: 0 });
        fireEvent.keyDown(document.body, { key: "k" });
        expect(await screen.findByText("Kuyrukta önceki kayıt yok.")).toBeInTheDocument();
        expect(push).not.toHaveBeenCalled();
    });

    describe("reject", () => {
        it("keeps the button off while the note is blank and shows the error when submitted blank", async () => {
            setup();
            await userEvent.click(screen.getByRole("button", { name: /^Reddet/ }));
            const dialog = screen.getByRole("dialog", { name: "Kararı reddet" });
            const submit = within(dialog).getByRole("button", { name: "Reddet" });
            expect(submit).toBeDisabled();
            await userEvent.type(within(dialog).getByLabelText("Ret notu"), "   ");
            expect(submit).toBeDisabled();
            fireEvent.submit(within(dialog).getByLabelText("Ret notu").closest("form")!);
            expect(await within(dialog).findByText("Ret notu zorunludur.")).toBeInTheDocument();
            expect(POST).not.toHaveBeenCalled();
        });

        it("sends the trimmed note", async () => {
            setup();
            fireEvent.keyDown(document.body, { key: "r" });
            const dialog = await screen.findByRole("dialog", { name: "Kararı reddet" });
            await userEvent.type(within(dialog).getByLabelText("Ret notu"), "  Yanlış karar  ");
            await userEvent.click(within(dialog).getByRole("button", { name: "Reddet" }));
            await waitFor(() => expect(push).toHaveBeenCalled());
            expect(posted()).toEqual({ action: "reject", note: "Yanlış karar" });
            expect(push).toHaveBeenCalledWith(`/kararlar/${NEXT}?band=low&pos=4&flash=rejected`);
        });

        it("closes on Escape and gives the focus back to the button", async () => {
            setup();
            const trigger = screen.getByRole("button", { name: /^Reddet/ });
            trigger.focus();
            await userEvent.click(trigger);
            const dialog = screen.getByRole("dialog");
            fireEvent(dialog, new Event("cancel", { cancelable: true }));
            await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
            expect(trigger).toHaveFocus();
        });

        it("gives the focus back to the Reddet button when a shortcut opened it", async () => {
            setup();
            expect(document.body).toHaveFocus();
            fireEvent.keyDown(document.body, { key: "r" });
            const dialog = await screen.findByRole("dialog");
            fireEvent(dialog, new Event("cancel", { cancelable: true }));
            await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
            expect(screen.getByRole("button", { name: /^Reddet/ })).toHaveFocus();
        });

        it("starts empty every time it opens", async () => {
            setup();
            const open = async () => {
                fireEvent.keyDown(document.body, { key: "r" });
                return screen.findByRole("dialog");
            };
            let dialog = await open();
            await userEvent.type(within(dialog).getByLabelText("Ret notu"), "eski not");
            await userEvent.click(within(dialog).getByRole("button", { name: "Vazgeç" }));
            await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
            dialog = await open();
            expect(within(dialog).getByLabelText("Ret notu")).toHaveValue("");
        });

        it("ignores Escape and Vazgeç while the request is on its way", async () => {
            let finish: (value: unknown) => void = () => {};
            POST.mockReset();
            POST.mockReturnValue(new Promise((resolve) => (finish = resolve)));
            setup();
            fireEvent.keyDown(document.body, { key: "r" });
            const dialog = await screen.findByRole("dialog");
            await userEvent.type(within(dialog).getByLabelText("Ret notu"), "neden");
            await userEvent.click(within(dialog).getByRole("button", { name: "Reddet" }));
            await waitFor(() => expect(POST).toHaveBeenCalled());
            const event = new Event("cancel", { cancelable: true });
            fireEvent(dialog, event);
            expect(event.defaultPrevented).toBe(true);
            expect(screen.getByRole("dialog")).toBeInTheDocument();
            expect(within(dialog).getByRole("button", { name: "Vazgeç" })).toBeDisabled();
            finish(done);
            await waitFor(() => expect(push).toHaveBeenCalled());
        });
    });

    describe("edit", () => {
        async function startEdit() {
            setup();
            await userEvent.click(screen.getByRole("button", { name: /^Düzelt ve onayla/ }));
        }

        it("turns the fields card into a form with the same labels and cancels back to the read view", async () => {
            await startEdit();
            for (const label of [
                "Mahkeme",
                "Daire",
                "Esas no",
                "Karar no",
                "Karar tarihi",
                "Sonuç",
                "Anahtar kelimeler",
            ]) {
                expect(screen.getByLabelText(label)).toBeInTheDocument();
            }
            expect(screen.getByLabelText("Karar tarihi")).toHaveAttribute("type", "date");
            await userEvent.click(screen.getByRole("button", { name: "Vazgeç" }));
            expect(screen.queryByLabelText("Esas no")).not.toBeInTheDocument();
            expect(screen.getByText("2019/1234")).toBeInTheDocument();
        });

        it("says there is nothing to send when nothing changed", async () => {
            await startEdit();
            await userEvent.click(
                screen.getByRole("button", { name: "Değişiklikleri gözden geçir" }),
            );
            expect(screen.getByText("Değişen alan yok.")).toBeInTheDocument();
            expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
        });

        it("marks fields that were emptied or are not valid and sends nothing", async () => {
            await startEdit();
            await userEvent.clear(screen.getByLabelText("Karar no"));
            await userEvent.clear(screen.getByLabelText("Daire"));
            await userEvent.click(
                screen.getByRole("button", { name: "Değişiklikleri gözden geçir" }),
            );
            expect(screen.getByLabelText("Karar no")).toBeInvalid();
            expect(screen.getByText("Boş bırakılamaz.")).toBeInTheDocument();
            expect(screen.getByText(/Boş bırakılan alan değişmez/)).toBeInTheDocument();
            expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
        });

        it("summarises the changes in a dialog and sends only the changed fields", async () => {
            await startEdit();
            await userEvent.clear(screen.getByLabelText("Karar no"));
            await userEvent.type(screen.getByLabelText("Karar no"), "2021/999");
            await userEvent.selectOptions(screen.getByLabelText("Sonuç"), "bozma");
            await userEvent.clear(screen.getByLabelText("Anahtar kelimeler"));
            await userEvent.type(
                screen.getByLabelText("Anahtar kelimeler"),
                "fesih{Enter}{Enter} ihbar ",
            );
            await userEvent.type(screen.getByLabelText("Maddeler (virgülle)"), ", 20");
            await userEvent.click(screen.getByRole("button", { name: "Satır ekle" }));
            const [, newStatute] = screen.getAllByLabelText("Kanun no");
            await userEvent.type(newStatute!, "6331");
            await userEvent.type(screen.getAllByLabelText("Maddeler (virgülle)")[1]!, "4");
            await userEvent.click(
                screen.getByRole("button", { name: "Değişiklikleri gözden geçir" }),
            );

            const dialog = screen.getByRole("dialog", { name: "Düzeltmeleri onayla" });
            expect(within(dialog).getByText("Karar no: 2021/567 → 2021/999")).toBeInTheDocument();
            expect(within(dialog).getByText("Sonuç: Onama → Bozma")).toBeInTheDocument();
            expect(
                within(dialog).getByText("Anahtar kelimeler: fesih → fesih, ihbar"),
            ).toBeInTheDocument();
            expect(
                within(dialog).getByText(
                    /İlgili kanun ve maddeler: 4857 s\. Kanun m\. 18 → 4857 s\. Kanun m\. 18, 20; 6331 s\. Kanun m\. 4/,
                ),
            ).toBeInTheDocument();
            expect(within(dialog).queryByText(/Mahkeme:/)).not.toBeInTheDocument();

            await userEvent.type(
                within(dialog).getByLabelText("Not (isteğe bağlı)"),
                " yazım hatası ",
            );
            await userEvent.click(
                within(dialog).getByRole("button", { name: "Düzelterek onayla" }),
            );
            await waitFor(() => expect(push).toHaveBeenCalled());
            expect(posted()).toEqual({
                action: "edit",
                note: "yazım hatası",
                edits: {
                    karar_no: "2021/999",
                    outcome: "bozma",
                    keywords: ["fesih", "ihbar"],
                    related_articles: [
                        {
                            statute: 4857,
                            label: "4857 SK",
                            articles: ["18", "20"],
                            raw: "4857 S. İşK/18",
                        },
                        { statute: 6331, label: "", articles: ["4"], raw: "" },
                    ],
                },
            });
            expect(push).toHaveBeenCalledWith(expect.stringContaining("flash=edited"));
        });

        it("marks the fields named by a 422 and lets the reviewer fix them", async () => {
            POST.mockResolvedValue({
                error: {
                    error: { code: "validation_error", params: { fields: ["edits.karar_no"] } },
                },
            });
            await startEdit();
            await userEvent.type(screen.getByLabelText("Karar no"), "9");
            await userEvent.click(
                screen.getByRole("button", { name: "Değişiklikleri gözden geçir" }),
            );
            await userEvent.click(screen.getByRole("button", { name: "Düzelterek onayla" }));
            await waitFor(() => expect(screen.getByLabelText("Karar no")).toBeInvalid());
            expect(screen.getByText("Bu değer kabul edilmedi.")).toBeInTheDocument();
            expect(screen.getByLabelText("Esas no")).not.toBeInvalid();
            expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
            expect(push).not.toHaveBeenCalled();
        });

        it("lets the reviewer clear the marker of a field by editing it", async () => {
            POST.mockReset();
            POST.mockResolvedValue({
                error: {
                    error: {
                        code: "validation_error",
                        params: { fields: ["edits.karar_no", "edits.esas_no"] },
                    },
                },
            });
            await startEdit();
            await userEvent.type(screen.getByLabelText("Karar no"), "9");
            await userEvent.type(screen.getByLabelText("Esas no"), "9");
            await userEvent.click(
                screen.getByRole("button", { name: "Değişiklikleri gözden geçir" }),
            );
            await userEvent.click(screen.getByRole("button", { name: "Düzelterek onayla" }));
            await waitFor(() => expect(screen.getByLabelText("Karar no")).toBeInvalid());
            await userEvent.type(screen.getByLabelText("Karar no"), "0");
            expect(screen.getByLabelText("Karar no")).not.toBeInvalid();
            expect(screen.getByLabelText("Esas no")).toBeInvalid();
            expect(screen.getAllByText("Bu değer kabul edilmedi.")).toHaveLength(1);
        });

        it("points the inputs of an article row with a bad statute to its error", async () => {
            await startEdit();
            await userEvent.type(screen.getByLabelText("Kanun no"), "x");
            await userEvent.click(
                screen.getByRole("button", { name: "Değişiklikleri gözden geçir" }),
            );
            const message = screen.getByText("Kanun numarası yalnızca rakamlardan oluşmalı.");
            for (const input of [
                screen.getByLabelText("Kanun no"),
                screen.getByLabelText("Maddeler (virgülle)"),
            ]) {
                expect(input).toBeInvalid();
                expect(input.getAttribute("aria-describedby")).toBe(message.parentElement?.id);
            }
            await userEvent.type(screen.getByLabelText("Kanun no"), "1");
            expect(screen.getByLabelText("Kanun no")).not.toBeInvalid();
            expect(screen.getByLabelText("Kanun no")).not.toHaveAttribute("aria-describedby");
        });

        it("maps a 422 on an entry of the article list to its row", async () => {
            POST.mockReset();
            POST.mockResolvedValue({
                error: {
                    error: {
                        code: "validation_error",
                        params: { fields: ["edits.related_articles.1.statute"] },
                    },
                },
            });
            await startEdit();
            await userEvent.click(screen.getByRole("button", { name: "Satır ekle" }));
            await userEvent.type(screen.getAllByLabelText("Kanun no")[1]!, "6331");
            await userEvent.click(
                screen.getByRole("button", { name: "Değişiklikleri gözden geçir" }),
            );
            await userEvent.click(screen.getByRole("button", { name: "Düzelterek onayla" }));
            await waitFor(() => expect(screen.getAllByLabelText("Kanun no")[1]).toBeInvalid());
            expect(screen.getAllByLabelText("Kanun no")[0]).not.toBeInvalid();
            expect(screen.getAllByLabelText("Maddeler (virgülle)")[1]).toBeInvalid();
            expect(screen.getAllByLabelText("Kanun no")[1]).toHaveAttribute("aria-describedby");
        });

        it("empties the note of the confirm dialog when it is closed", async () => {
            await startEdit();
            const review = () =>
                userEvent.click(
                    screen.getByRole("button", { name: "Değişiklikleri gözden geçir" }),
                );
            await userEvent.type(screen.getByLabelText("Karar no"), "9");
            await review();
            await userEvent.type(screen.getByLabelText("Not (isteğe bağlı)"), "eski not");
            await userEvent.click(
                within(screen.getByRole("dialog")).getByRole("button", { name: "Vazgeç" }),
            );
            await review();
            expect(screen.getByLabelText("Not (isteğe bağlı)")).toHaveValue("");
        });

        it("gives the focus back to the Düzelt ve onayla button when the edit is cancelled", async () => {
            setup();
            fireEvent.keyDown(document.body, { key: "e" });
            await userEvent.click(await screen.findByRole("button", { name: "Vazgeç" }));
            expect(screen.getByRole("button", { name: /^Düzelt ve onayla/ })).toHaveFocus();
        });

        it("shows a general message when the publish refused the values and no field is named", async () => {
            POST.mockResolvedValue({
                error: { error: { code: "validation_error", params: { fields: [] } } },
            });
            await startEdit();
            await userEvent.type(screen.getByLabelText("Karar no"), "9");
            await userEvent.click(
                screen.getByRole("button", { name: "Değişiklikleri gözden geçir" }),
            );
            await userEvent.click(screen.getByRole("button", { name: "Düzelterek onayla" }));
            expect(
                await screen.findByText(
                    "Kayıt bu değerlerle yayınlanamadı. Alanları kontrol edin.",
                ),
            ).toBeInTheDocument();
            expect(screen.getByLabelText("Karar no")).not.toBeInvalid();
        });
    });

    describe("errors", () => {
        it("review_conflict says someone else was first and offers a refresh", async () => {
            POST.mockResolvedValue({ error: { error: { code: "review_conflict", params: {} } } });
            setup();
            await userEvent.click(screen.getByRole("button", { name: /^Onayla/ }));
            const alert = await screen.findByRole("alert");
            expect(alert).toHaveTextContent("Bu kaydı az önce başka biri işledi.");
            await userEvent.click(within(alert).getByRole("button", { name: "Sayfayı yenile" }));
            expect(refresh).toHaveBeenCalled();
            expect(push).not.toHaveBeenCalled();
            expect(screen.getByRole("button", { name: /^Onayla/ })).toBeEnabled();
        });

        it("decision_conflict shows the id of the published decision in mono", async () => {
            POST.mockResolvedValue({
                error: { error: { code: "decision_conflict", params: { decision_id: "dec-77" } } },
            });
            setup();
            await userEvent.click(screen.getByRole("button", { name: /^Onayla/ }));
            const alert = await screen.findByRole("alert");
            expect(alert).toHaveTextContent("zaten yayınlanmış");
            expect(within(alert).getByText("dec-77")).toHaveClass("font-mono");
        });

        it("other codes get the generic message from the error hook", async () => {
            POST.mockResolvedValue({ error: { error: { code: "internal_error", params: {} } } });
            setup();
            await userEvent.click(screen.getByRole("button", { name: /^Onayla/ }));
            expect(await screen.findByRole("alert")).toHaveTextContent("Beklenmeyen bir hata");
        });

        it("a lost session leaves for the session-end page", async () => {
            POST.mockResolvedValue({ error: { error: { code: "unauthorized", params: {} } } });
            setup();
            await userEvent.click(screen.getByRole("button", { name: /^Onayla/ }));
            await waitFor(() => expect(push).toHaveBeenCalledWith("/oturum-sonu"));
        });
    });
});
