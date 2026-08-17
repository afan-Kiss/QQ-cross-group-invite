import { useMemo, useState } from "react";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ChevronLeft, ChevronRight, RefreshCw, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Member, MemberStatus } from "@/lib/types";
import { cn, formatNumber } from "@/lib/utils";
import { useInviteStore } from "@/store/useInviteStore";

const roleLabel = { owner: "Ⱥ��", admin: "����Ա", member: "��Ա" } as const;

const statusLabel: Record<MemberStatus, string> = {
  success: "����ɹ�",
  filtered: "�ѹ��ˣ�����Ա��",
  rate_limited: "Ƶ������",
  failed: "����ʧ��",
  waiting: "�ȴ���",
  inviting: "������",
};

function statusVariant(status: MemberStatus) {
  return status as "success" | "filtered" | "rate_limited" | "failed" | "waiting" | "inviting";
}

export function MemberTable() {
  const members = useInviteStore((s) => s.members);
  const membersLoaded = useInviteStore((s) => s.membersLoaded);
  const selectedQqs = useInviteStore((s) => s.selectedQqs);
  const toggleSelect = useInviteStore((s) => s.toggleSelect);
  const toggleSelectAll = useInviteStore((s) => s.toggleSelectAll);
  const stats = useInviteStore((s) => s.stats);

  const [globalFilter, setGlobalFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const filteredMembers = useMemo(() => {
    if (statusFilter === "all") return members;
    return members.filter((m) => m.status === statusFilter);
  }, [members, statusFilter]);

  const columns = useMemo<ColumnDef<Member>[]>(
    () => [
      {
        id: "select",
        header: ({ table }) => (
          <Checkbox
            checked={
              table.getRowModel().rows.length > 0 &&
              table.getRowModel().rows.every((row) => selectedQqs.has(row.original.qq))
            }
            onCheckedChange={() =>
              toggleSelectAll(table.getRowModel().rows.map((r) => r.original.qq))
            }
          />
        ),
        cell: ({ row }) => (
          <Checkbox
            checked={selectedQqs.has(row.original.qq)}
            onCheckedChange={() => toggleSelect(row.original.qq)}
          />
        ),
        size: 40,
      },
      {
        accessorKey: "qq",
        header: "QQ��",
        cell: ({ getValue }) => (
          <span className="font-mono text-[13px]">{getValue<number>()}</span>
        ),
      },
      {
        accessorKey: "nickname",
        header: "�ǳ�",
      },
      {
        accessorKey: "role",
        header: "��ɫ",
        cell: ({ getValue }) => {
          const role = getValue<Member["role"]>();
          return <Badge variant={role}>{roleLabel[role]}</Badge>;
        },
      },
      {
        accessorKey: "status",
        header: "״̬",
        cell: ({ row }) => {
          const status = row.original.status;
          const label =
            status === "filtered" && row.original.filterReason
              ? `�ѹ��ˣ�${row.original.filterReason}��`
              : statusLabel[status];
          return <Badge variant={statusVariant(status)}>{label}</Badge>;
        },
      },
      {
        id: "action",
        header: "����",
        cell: ({ row }) => {
          const status = row.original.status;
          if (status === "success")
            return (
              <button className="text-[13px] text-primary hover:underline">�鿴</button>
            );
          if (status === "rate_limited")
            return (
              <button className="text-[13px] text-[#b8860b] hover:underline">����</button>
            );
          if (status === "failed")
            return (
              <button className="text-[13px] text-danger hover:underline">����</button>
            );
          return <span className="text-muted-foreground">��</span>;
        },
      },
    ],
    [selectedQqs, toggleSelect, toggleSelectAll],
  );

  const table = useReactTable({
    data: filteredMembers,
    columns,
    state: { globalFilter },
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 20 } },
  });

  const pageQqs = table.getRowModel().rows.map((r) => r.original.qq);
  const allPageSelected =
    pageQqs.length > 0 && pageQqs.every((qq) => selectedQqs.has(qq));

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h3 className="text-[15px] font-semibold text-[#2f352d]">
            ��Ա�б����� {formatNumber(stats.total || members.length)} �ˣ�
          </h3>
          {membersLoaded && (
            <span className="rounded-full bg-primary-light px-2.5 py-0.5 text-xs font-medium text-primary">
              �Ѽ���
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={globalFilter}
              onChange={(e) => setGlobalFilter(e.target.value)}
              placeholder="����QQ�Ż��ǳ�"
              className="w-[200px] pl-9"
            />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[120px]">
              <SelectValue placeholder="ȫ��״̬" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">ȫ��״̬</SelectItem>
              <SelectItem value="waiting">�ȴ���</SelectItem>
              <SelectItem value="success">����ɹ�</SelectItem>
              <SelectItem value="rate_limited">Ƶ������</SelectItem>
              <SelectItem value="failed">����ʧ��</SelectItem>
              <SelectItem value="filtered">�ѹ���</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="secondary" size="sm">
            <RefreshCw className="h-3.5 w-3.5" />
            ˢ��
          </Button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto rounded-[12px] border border-border">
        <table className="w-full min-w-[720px] border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-[#f9faf8]">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="border-b border-border">
                {hg.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-3 py-3 text-[13px] font-medium text-muted-foreground"
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                className="border-b border-border/70 transition-colors duration-150 hover:bg-[#f7f9f5]"
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-3 py-2.5">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
          <Checkbox
            checked={allPageSelected}
            onCheckedChange={() => toggleSelectAll(pageQqs)}
          />
          <span>ȫѡ����ѡ {formatNumber(selectedQqs.size)} �</span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-1">
            {Array.from({ length: Math.min(5, table.getPageCount()) }, (_, i) => {
              const page = i + 1;
              return (
                <button
                  key={page}
                  type="button"
                  onClick={() => table.setPageIndex(page - 1)}
                  className={cn(
                    "flex h-8 min-w-8 items-center justify-center rounded-[8px] px-2 text-[13px] transition-colors duration-150",
                    table.getState().pagination.pageIndex === page - 1
                      ? "bg-primary text-white"
                      : "text-muted-foreground hover:bg-[#eef1eb]",
                  )}
                >
                  {page}
                </button>
              );
            })}
            {table.getPageCount() > 5 && (
              <span className="px-1 text-muted-foreground">�� {table.getPageCount()}</span>
            )}
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Select
            value={String(table.getState().pagination.pageSize)}
            onValueChange={(v) => table.setPageSize(Number(v))}
          >
            <SelectTrigger className="w-[100px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="20">20 ��/ҳ</SelectItem>
              <SelectItem value="50">50 ��/ҳ</SelectItem>
              <SelectItem value="100">100 ��/ҳ</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  );
}
