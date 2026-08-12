"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  addWatchlistItem,
  createCompany,
  createWatchlist,
  deleteWatchlist,
  getWatchlists,
  getWatchlistItems,
  removeWatchlistItem,
  searchCompanies,
  updateWatchlist,
} from "../../lib/api";

type Watchlist = Awaited<ReturnType<typeof getWatchlists>>[number];

export default function WatchlistManager() {
  const [lists, setLists] = useState<Watchlist[]>([]);
  const [name, setName] = useState("");
  const [symbol, setSymbol] = useState("");
  const [market, setMarket] = useState<"TW" | "US">("TW");
  const [companyName, setCompanyName] = useState("");
  const [selectedList, setSelectedList] = useState<number>();
  const [matches, setMatches] = useState<Awaited<ReturnType<typeof searchCompanies>>>([]);
  const [searched, setSearched] = useState(false);
  const [message, setMessage] = useState("");
  const [items, setItems] = useState<Record<number, Awaited<ReturnType<typeof getWatchlistItems>>>>({});
  const [editingListId, setEditingListId] = useState<number>();
  const [editingName, setEditingName] = useState("");
  const [editingDescription, setEditingDescription] = useState("");

  async function refresh() {
    const nextLists = await getWatchlists();
    setLists(nextLists);
    const entries = await Promise.all(nextLists.map(async (list) => [list.id, await getWatchlistItems(list.id)] as const));
    setItems(Object.fromEntries(entries));
  }

  useEffect(() => {
    refresh().catch(() => setMessage("自選清單服務暫時無法使用。"));
  }, []);

  async function submitList(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    try {
      await createWatchlist(name.trim());
      setName("");
      setMessage("已建立自選清單。");
      await refresh();
    } catch {
      setMessage("無法建立自選清單。");
    }
  }

  async function search(event: FormEvent) {
    event.preventDefault();
    if (!symbol.trim()) return;
    try {
      const query = symbol.trim();
      setMatches(await searchCompanies(query));
      setMarket(/^\d{4,6}$/.test(query) ? "TW" : "US");
      setSearched(true);
    } catch {
      setMessage("目前無法搜尋。");
    }
  }

  async function createAndAdd() {
    const symbolToAdd = symbol.trim().toUpperCase();
    if (!symbolToAdd) return;
    if (!selectedList) {
      setMessage("請先選擇自選清單。");
      return;
    }
    try {
      await createCompany({
        symbol: symbolToAdd,
        market,
        company_name: companyName.trim() || undefined,
      });
      await add(symbolToAdd);
      setCompanyName("");
      setSearched(false);
    } catch {
      setMessage("無法建立公司，可能已存在。");
    }
  }

  async function add(symbolToAdd: string) {
    if (!selectedList) {
      setMessage("請先選擇自選清單。");
      return;
    }
    try {
      await addWatchlistItem(selectedList, symbolToAdd);
      setMessage(`已加入 ${symbolToAdd}。`);
      setMatches([]);
      setSymbol("");
      await refresh();
    } catch {
      setMessage("無法加入標的。");
    }
  }

  async function removeItem(watchlistId: number, instrumentId: number) {
    try {
      await removeWatchlistItem(watchlistId, instrumentId);
      setItems((current) => ({ ...current, [watchlistId]: (current[watchlistId] ?? []).filter((item) => item.instrument_id !== instrumentId) }));
    } catch {
      setMessage("無法移除標的。");
    }
  }

  async function remove(id: number) {
    try {
      await deleteWatchlist(id);
      setMessage("已刪除自選清單。");
      await refresh();
    } catch {
      setMessage("無法刪除自選清單。");
    }
  }

  function startEditing(list: Watchlist) {
    setEditingListId(list.id);
    setEditingName(list.name);
    setEditingDescription(list.description ?? "");
    setMessage("");
  }

  function cancelEditing() {
    setEditingListId(undefined);
    setEditingName("");
    setEditingDescription("");
  }

  async function saveList(event: FormEvent, watchlistId: number) {
    event.preventDefault();
    const trimmedName = editingName.trim();
    if (!trimmedName) {
      setMessage("請輸入自選清單名稱。");
      return;
    }
    try {
      await updateWatchlist(watchlistId, {
        name: trimmedName,
        description: editingDescription.trim() || null,
      });
      cancelEditing();
      setMessage("已更新自選清單。");
      await refresh();
    } catch {
      setMessage("無法更新自選清單。名稱可能已存在。");
    }
  }

  return (
    <section className="history-block">
      <div className="eyebrow">管理追蹤標的</div>
      <form className="toolbar" onSubmit={submitList}>
        <input aria-label="自選清單名稱" value={name} onChange={(event) => setName(event.target.value)} placeholder="新增自選清單" />
        <button className="pill selected" type="submit">建立</button>
      </form>
      <form className="toolbar" onSubmit={search}>
        <select aria-label="目標自選清單" value={selectedList ?? ""} onChange={(event) => setSelectedList(Number(event.target.value))}>
          <option value="">選擇清單</option>
          {lists.map((list) => <option key={list.id} value={list.id}>{list.name}</option>)}
        </select>
        <input aria-label="公司搜尋" value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="股票代號或公司名稱" />
        <button className="pill" type="submit">搜尋</button>
      </form>
      {matches.map((match) => <div className="change result-row" key={match.id}>
        <i className="rail neutral" />
        <div className="ticker">{match.symbol}</div>
        <div className="metric">{match.company_name}<span>{match.market} / {match.exchange ?? "市場"}</span></div>
        <button className="pill selected" onClick={() => add(match.symbol)}>加入</button>
      </div>)}
      {searched && !matches.length && symbol.trim() && <div className="change result-row">
        <i className="rail neutral" />
        <div className="ticker">{symbol.trim().toUpperCase()}</div>
        <div className="metric">尚未追蹤<span>建立後即可加入選定的自選清單。</span></div>
        <select aria-label="公司市場" value={market} onChange={(event) => setMarket(event.target.value as "TW" | "US")}>
          <option value="TW">台股</option>
          <option value="US">美股</option>
        </select>
        <input aria-label="公司名稱" value={companyName} onChange={(event) => setCompanyName(event.target.value)} placeholder="公司名稱（選填）" />
        <button className="pill selected" onClick={createAndAdd}>建立並加入</button>
      </div>}
      {lists.map((list) => <div className="change management-row" key={list.id}>
        <i className="rail neutral" />
        {editingListId === list.id ? <form className="toolbar" onSubmit={(event) => saveList(event, list.id)}>
          <input aria-label="自選清單名稱" value={editingName} onChange={(event) => setEditingName(event.target.value)} placeholder="自選清單名稱" />
          <input aria-label="自選清單說明" value={editingDescription} onChange={(event) => setEditingDescription(event.target.value)} placeholder="說明（選填）" />
          <button className="pill selected" type="submit">儲存</button>
          <button className="pill" type="button" onClick={cancelEditing}>取消</button>
        </form> : <>
          <div className="ticker">{list.name}</div>
          <div className="metric">{list.description ?? "無說明"}</div>
          <button className="pill" type="button" onClick={() => startEditing(list)}>編輯</button>
          <button className="pill" type="button" onClick={() => remove(list.id)}>刪除</button>
        </>}
        <div className="watchlist-items"><div className="history-list">{(items[list.id] ?? []).map((item) => <div className="history-row" key={item.instrument_id}><span className="history-metric">{item.symbol}</span><span>{item.company_name}</span><button className="pill" onClick={() => removeItem(list.id, item.instrument_id)}>移除</button></div>)}</div></div>
      </div>)}
      {message && <div className="empty">{message}</div>}
    </section>
  );
}
