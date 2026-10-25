import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

function stubFetch() {
  const fetchMock = vi.fn().mockResolvedValue(new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const requestedPath = (fetchMock: ReturnType<typeof vi.fn>) => new URL(fetchMock.mock.calls[0][0] as string).pathname + new URL(fetchMock.mock.calls[0][0] as string).search;

describe("appointment list requests", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("asks for cancelled appointments only when requested (patient history)", async () => {
    let fetchMock = stubFetch();
    await api.listAllAppointments("tok");
    expect(requestedPath(fetchMock)).toBe("/appointments/all");

    fetchMock = stubFetch();
    await api.listAllAppointments("tok", true);
    expect(requestedPath(fetchMock)).toBe("/appointments/all?include_cancelled=true");
  });

  it("includes cancelled appointments in the doctor's week", async () => {
    let fetchMock = stubFetch();
    await api.doctorAllAppointments("tok", "2026-10-26");
    expect(requestedPath(fetchMock)).toBe("/doctor/appointments/all?include_cancelled=true&from_date=2026-10-26");

    fetchMock = stubFetch();
    await api.doctorAllAppointments("tok");
    expect(requestedPath(fetchMock)).toBe("/doctor/appointments/all?include_cancelled=true");
  });
});
