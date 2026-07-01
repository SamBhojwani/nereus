import { useState } from "react";

export default function SearchBar({ onSearch }) {
  const [value, setValue] = useState("");
  return (
    <form
      className="searchbar"
      onSubmit={(e) => { e.preventDefault(); onSearch(value); }}
    >
      <input
        type="search"
        placeholder="Search a topic — elections, climate, a team…"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        aria-label="Search topic"
      />
      <button type="submit">Search</button>
    </form>
  );
}
