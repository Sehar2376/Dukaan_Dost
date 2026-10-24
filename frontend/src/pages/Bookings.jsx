import { niceStamp, niceTime, useApi } from "../api.js";
import { Badge, Card, Empty, ErrorBox, Loading, Table } from "../components/ui.jsx";

export default function Bookings() {
  const { data, error, loading } = useApi("/bookings");
  return (
    <Card title={`Bookings${data ? ` (${data.length})` : ""}`}>
      <ErrorBox error={error} />
      <p className="mb-3 text-xs text-slate-500">Appointments the assistant booked (cake tastings, fittings…). Times are checked against shop hours in code.</p>
      {loading && !data ? <Loading /> : !data?.length ? <Empty>No bookings yet. Customers can ask in the chat, e.g. “Saturday 5 baje tasting book kar dein”.</Empty> : (
        <Table head={["When", "Service", "Customer", "Status", "Booked on"]}>
          {data.map((b) => (
            <tr key={b.id}>
              <td className="px-3 py-2 font-medium">{niceTime(b.date_time)}</td>
              <td className="px-3 py-2">{b.service}</td>
              <td className="px-3 py-2">{b.customer_name || "—"}<div className="text-xs text-slate-500">{b.phone_masked}</div></td>
              <td className="px-3 py-2"><Badge color={b.status === "cancelled" ? "red" : "green"}>{b.status}</Badge></td>
              <td className="px-3 py-2 text-xs text-slate-500">{niceStamp(b.created_at)}</td>
            </tr>
          ))}
        </Table>
      )}
    </Card>
  );
}
