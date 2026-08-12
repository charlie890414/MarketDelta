"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  addWatchlistItem,
  createWatchlist,
  deleteWatchlist,
  getWatchlists,
  searchCompanies,
} from "../../lib/api";

type Watchlist = Awaited<ReturnType<typeof getWatchlists>>[number];

export default function WatchlistManager() {
  const [lists, setLists] = useState<Watchlist[]>([]);
  const [name, setName] = useState("");
  const [symbol, setSymbol] = useState("");
  const [selectedList, setSelectedList] = useState<number>();
  const [matches, setMatches] = useState<Awaited<ReturnType<typeof searchCompanies>>>([]);
  const [message, setMessage] = useState("");

  async function refresh() {
    setLists(await getWatchlists());
  }

  useEffect(() => {
    refresh().catch(() => setMessage("Watchlist service unavailable."));
  }, []);

  async function submitList(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    try {
      await createWatchlist(name.trim());
      setName("");
      setMessage("Watchlist created.");
      await refresh();
    } catch {
      setMessage("Could not create watchlist.");
    }
  }

  async function search(event: FormEvent) {
    event.preventDefault();
    if (!symbol.trim()) return;
    try {
      setMatches(await searchCompanies(symbol.trim()));
    } catch {
      setMessage("Search unavailable.");
    }
  }

  async function add(symbolToAdd: string) {
    if (!selectedList) {
      setMessage("Choose a watchlist first.");
      return;
    }
    try {
      await addWatchlistItem(selectedList, symbolToAdd);
      setMessage(`${symbolToAdd} added.`);
      setMatches([]);
      setSymbol("");
    } catch {
      setMessage("Could not add instrument.");
    }
  }

  async function remove(id: number) {
    try {
      await deleteWatchlist(id);
      setMessage("Watchlist deleted.");
      await refresh();
    } catch {
      setMessage("Could not delete watchlist.");
    }
  }

  return (
    <section className="history-block">
      <div className="eyebrow">Manage tracked universe</div>
      <form className="toolbar" onSubmit={submitList}>
        <input aria-label="Watchlist name" value={name} onChange={(event) => setName(event.target.value)} placeholder="New watchlist" />
        <button className="pill selected" type="submit">CREATE</button>
      </form>
      <form className="toolbar" onSubmit={search}>
        <select aria-label="Target watchlist" value={selectedList ?? ""} onChange={(event) => setSelectedList(Number(event.target.value))}>
          <option value="">Choose list</option>
          {lists.map((list) => <option key={list.id} value={list.id}>{list.name}</option>)}
        </select>
        <input aria-label="Company search" value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="Ticker or company" />
        <button className="pill" type="submit">SEARCH</button>
      </form>
      {matches.map((match) => <div className="change" key={match.id}>
        <div className="ticker">{match.symbol}</div>
        <div className="metric">{match.company_name}<span>{match.market} / {match.exchange ?? "market"}</span></div>
        <button className="pill selected" onClick={() => add(match.symbol)}>ADD</button>
      </div>)}
      {lists.map((list) => <div className="change" key={list.id}>
        <div className="ticker">{list.name}</div>
        <div className="metric">{list.description ?? "No description"}</div>
        <button className="pill" onClick={() => remove(list.id)}>DELETE</button>
      </div>)}
      {message && <div className="empty">{message}</div>}
    </section>
  );
}
