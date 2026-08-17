import { useEffect, useMemo, useState } from "react";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ChevronLeft, ChevronRight, Eye, EyeOff, RefreshCw, Search } from "lucide-react";
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
import { cn, formatNumber, maskToken } from "@/lib/utils";
import { useInviteStore } from "@/store/useInviteStore";
import { useSettingsStore } from "@/store/useSettingsStore";
import { MemberDetailDrawer } from "@/components/dashboard/MemberDetailDrawer";
import { MemberContextMenu } from "@/components/dashboard/MemberContextMenu";
import { toast } from "@/store/useToastStore";

const roleLabel = { owner: "群主", admin: "管理员", member: "成员" } as const;

const statusLabel: Record<MemberStatus, string> = {
  success: "邀请成功",
  filtered: "已过滤",
  rate_limited: "频繁限制",
  failed: "邀请失败",
  waiting: "等待中",
  inviting: "邀请中",
};

function canSelect(status: MemberStatus) {
  return status === "waiting" || status === "failed" || status === "rate_limited";
}

export function MemberTable() {
  const members = useInviteStore((s) => s.members);
  const membersRevision = useInviteStore((s) => s.membersRevision);
  const membersLoaded = useInviteStore((s) => s.membersLoaded);
  const selectedQqs = useInviteStore((s) => s.selectedQqs);
  const toggleSelect = useInviteStore((s) => s.toggleSelect);
  const toggleSelectAll = useInviteStore((s) => s.toggleSelectAll);
  const setDetailMemberQq = useInviteStore((s) => s.setDetailMemberQq);
  const detailMemberQq = useInviteStore((s) => s.detailMemberQq);
  const refreshStatus = useInviteStore((s) => s.refreshStatus);
  const compactTable = useSettingsStore((s) => s.settings.compactTable);

  const [globalFilter, setGlobalFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [revealedTokens, setRevealedTokens] = useState<Set<number>>(new Set());

  useEffect(() => {
    setRevealedTokens(new Set());
  }, [membersRevision]);
  const [menu, setMenu] = useState<{ x: number; y: number; member: Member } | null>(null);

  const filteredMembers = useMemo(() => {
    if (statusFilter === "all") return members;
    return members.filter((m) => m.status === statusFilter);
  }, [members, statusFilter]);

  const columns = useMemo<ColumnDef<Member>[]>(
    () => [
      {
        id: "select",
        header: ({ table }) => {
          const rows = table.getRowModel().rows.filter((r) => canSelect(r.original.status));
          return (
            <Checkbox
              checked={rows.length > 0 && rows.every((row) => selectedQqs.has(row.original.qq))}
              onCheckedChange={() => toggleSelectAll(rows.map((r) => r.original.qq))}
            />
          );
        },
        cell: ({ row }) => (
          <Checkbox
            checked={selectedQqs.has(row.original.qq)}
            disabled={!canSelect(row.original.status)}
            onCheckedChange={() => toggleSelect(row.original.qq)}
            onClick={(e) => e.stopPropagation()}
          />
        ),
        size: 40,
      },
      {
        accessorKey: "qq",
        header: "QQ号",
        cell: ({ getValue }) => (
          <span className="font-mono text-[13px]">{getValue<number>()}</span>
        ),
      },
      {
        accessorKey: "nickname",
        header: "昵称",
      },
      {
        accessorKey: "card",
        header: "群名片",
        cell: ({ getValue }) => getValue<string>() || "—",
      },
      {
        accessorKey: "role",
        header: "角色",
        cell: ({ getValue }) => {
          const role = getValue<Member["role"]>();
          return <Badge variant={role}>{roleLabel[role]}</Badge>;
        },
      },
      {
        id: "token",
        header: "Token",
        cell: ({ row }) => {
          const token = row.original.token;
          const revealed = revealedTokens.has(row.original.qq);
          return (
            <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
              <span className="font-mono text-[12px] text-muted-foreground">
                {revealed ? token || "—" : maskToken(token)}
              </span>
              <button
                type="button"
                className="rounded p-1 text-muted-foreground hover:bg-[#eef1eb]"
                title={revealed ? "隐藏" : "显示"}
                onClick={() =>
                  setRevealedTokens((prev) => {
                    const next = new Set(prev);
                    if (next.has(row.original.qq)) next.delete(row.original.qq);
                    else next.add(row.original.qq);
                    return next;
                  })
                }
              >
                {revealed ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            </div>
          );
        },
      },
      {
        accessorKey: "status",
        header: "状态",
        cell: ({ row }) => {
          const status = row.original.status;
          const label =
            status === "filtered" && row.original.filterReason
              ? `已过滤（${row.original.filterReason}）`
              : statusLabel[status];
          return <Badge variant={status}>{label}</Badge>;
        },
      },
      {
        id: "action",
        header: "操作",
        cell: ({ row }) => (
          <button
            type="button"
            className="text-[13px] text-primary hover:underline"
            onClick={(e) => {
              e.stopPropagation();
              setDetailMemberQq(row.original.qq);
            }}
          >
            查看
          </button>
        ),
      },
    ],
    [selectedQqs, toggleSelect, toggleSelectAll, revealedTokens, setDetailMemberQq],
  );

  const table = useReactTable({
    data: filteredMembers,
    columns,
    state: { globalFilter },
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    globalFilterFn: (row, _columnId, filterValue) => {
      const q = String(filterValue).toLowerCase();
      if (!q) return true;
      return (
        String(row.original.qq).includes(q) ||
        row.original.nickname.toLowerCase().includes(q) ||
        (row.original.card || "").toLowerCase().includes(q)
      );
    },
    initialState: { pagination: { pageSize: 20 } },
  });

  const pageSelectable = table
    .getRowModel()
    .rows.filter((r) => canSelect(r.original.status))
    .map((r) => r.original.qq);
  const allPageSelected =
    pageSelectable.length > 0 && pageSelectable.every((qq) => selectedQqs.has(qq));

  useEffect(() => {
    if (detailMemberQq == null) {
      setRevealedTokens(new Set());
    }
  }, [detailMemberQq]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h3 className="text-[15px] font-semibold text-[#2f352d]">
            成员列表（共 {formatNumber(members.length)} 人）
          </h3>
          {membersLoaded && (
            <span className="rounded-full bg-primary-light px-2.5 py-0.5 text-xs font-medium text-primary">
              已加载
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={globalFilter}
              onChange={(e) => setGlobalFilter(e.target.value)}
              placeholder="搜索QQ号或昵称"
              className="w-[200px] pl-9"
            />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[120px]">
              <SelectValue placeholder="全部状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="waiting">等待中</SelectItem>
              <SelectItem value="success">邀请成功</SelectItem>
              <SelectItem value="rate_limited">频繁限制</SelectItem>
              <SelectItem value="failed">邀请失败</SelectItem>
              <SelectItem value="filtered">已过滤</SelectItem>
              <SelectItem value="inviting">邀请中</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              void refreshStatus();
              toast("info", "已刷新");
            }}
          >
            <RefreshCw className="h-3.5 w-3.5" />
            刷新
          </Button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto rounded-[12px] border border-border">
        <table className="w-full min-w-[860px] border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-[#f9faf8]">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="border-b border-border">
                {hg.headers.map((header) => (
                  <th
                    key={header.id}
                    className={cn(
                      "px-3 text-[13px] font-medium text-muted-foreground",
                      compactTable ? "py-2" : "py-3",
                    )}
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
                className={cn(
                  "border-b border-border/70 transition-colors duration-150 hover:bg-[#f7f9f5] cursor-pointer",
                  compactTable ? "[&>td]:py-1.5" : "[&>td]:py-2.5",
                )}
                onClick={() => setDetailMemberQq(row.original.qq)}
                onContextMenu={(e) => {
                  e.preventDefault();
                  setMenu({ x: e.clientX, y: e.clientY, member: row.original });
                }}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-3">
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
            onCheckedChange={() => toggleSelectAll(pageSelectable)}
          />
          <span>
            全选（已选 {formatNumber(selectedQqs.size)} 项）
          </span>
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
            {(() => {
              const pageCount = table.getPageCount();
              const current = table.getState().pagination.pageIndex;
              const windowSize = 5;
              let start = Math.max(0, current - Math.floor(windowSize / 2));
              let end = Math.min(pageCount, start + windowSize);
              start = Math.max(0, end - windowSize);
              return Array.from({ length: Math.max(0, end - start) }, (_, i) => {
                const page = start + i + 1;
                return (
                  <button
                    key={page}
                    type="button"
                    onClick={() => table.setPageIndex(page - 1)}
                    className={cn(
                      "flex h-8 min-w-8 items-center justify-center rounded-[8px] px-2 text-[13px] transition-colors duration-150",
                      current === page - 1
                        ? "bg-primary text-white"
                        : "text-muted-foreground hover:bg-[#eef1eb]",
                    )}
                  >
                    {page}
                  </button>
                );
              });
            })()}
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
              <SelectItem value="20">20条/页</SelectItem>
              <SelectItem value="50">50条/页</SelectItem>
              <SelectItem value="100">100条/页</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <MemberDetailDrawer />
      {menu && (
        <MemberContextMenu
          x={menu.x}
          y={menu.y}
          member={menu.member}
          onClose={() => setMenu(null)}
        />
      )}
    </div>
  );
}
