const state = {
  index: null,
  songs: [],
  selectedDifficulty: null,
  searchResults: [],
  sortKey: "title",
  sortDirection: "asc",
  listScrollY: 0,
};

const elements = {
  libraryStatus: document.querySelector("#libraryStatus"),
  searchInput: document.querySelector("#searchInput"),
  searchButton: document.querySelector("#searchButton"),
  songResults: document.querySelector("#songResults"),
  statusText: document.querySelector("#statusText"),
  listButton: document.querySelector("#listButton"),
  previewCover: document.querySelector("#previewCover"),
  previewCoverFrame: document.querySelector(".preview-cover"),
  previewTitle: document.querySelector("#previewTitle"),
  previewArtist: document.querySelector("#previewArtist"),
  previewDifficulty: document.querySelector("#previewDifficulty"),
  previewMeta: document.querySelector("#previewMeta"),
  imageStage: document.querySelector("#imageStage"),
  chartImage: document.querySelector("#chartImage"),
  imageLoading: document.querySelector("#imageLoading"),
  imageError: document.querySelector("#imageError"),
  emptyState: document.querySelector("#emptyState"),
};

const DIFFICULTY_COLUMNS = [
  { key: "00normal", label: "N", name: "Normal" },
  { key: "01hard", label: "H", name: "Hard" },
  { key: "02extreme", label: "E", name: "Expert" },
  { key: "03real", label: "R", name: "Real" },
];

function setStatus(text, kind = "") {
  elements.statusText.textContent = text;
  elements.statusText.className = `status-text ${kind}`.trim();
}

function setView(view) {
  document.body.dataset.view = view;
}

function sortDifficulties(difficulties) {
  return [...difficulties].sort((a, b) => Number(a.difficulty_number) - Number(b.difficulty_number));
}

function buildSongs(charts) {
  const songs = new Map();
  for (const chart of charts) {
    const song = songs.get(chart.basename) || {
      basename: chart.basename,
      title: chart.title || chart.basename,
      artist: chart.artist || "",
      difficulties: [],
    };
    song.difficulties.push(chart);
    songs.set(chart.basename, song);
  }

  return [...songs.values()]
    .map((song) => ({ ...song, difficulties: sortDifficulties(song.difficulties) }))
    .sort((a, b) => a.title.localeCompare(b.title, undefined, { sensitivity: "base" }));
}

function chartLabel(chart) {
  const isReal = chart.difficulty_name === "Real" || chart.difficulty_code === "03real";
  const level = isReal ? chart.display_level || "" : chart.display_level || chart.level || "";
  return `${chart.difficulty_name} ${level}`.trim();
}

function levelLabel(chart) {
  if (!chart) {
    return "";
  }
  const isReal = chart.difficulty_name === "Real" || chart.difficulty_code === "03real";
  const level = isReal ? chart.display_level || "" : chart.display_level || chart.level || "";
  if (!level) {
    return "";
  }
  return isReal ? `◇${level}` : level;
}

function chartLevelValue(chart) {
  if (!chart) {
    return null;
  }
  const isReal = chart.difficulty_name === "Real" || chart.difficulty_code === "03real";
  const level = isReal ? chart.display_level || "" : chart.display_level || chart.level || "";
  const value = Number(level);
  return Number.isFinite(value) ? value : null;
}

function chartByDifficulty(song, difficultyCode) {
  return song.difficulties.find((chart) => chart.difficulty_code === difficultyCode) || null;
}

function compareSongsByTitle(a, b) {
  return a.title.localeCompare(b.title, undefined, { sensitivity: "base" }) || a.basename.localeCompare(b.basename);
}

function compareSongsByArtist(a, b) {
  return (a.artist || "").localeCompare(b.artist || "", undefined, { sensitivity: "base" }) || compareSongsByTitle(a, b);
}

function compareSongsByLevel(a, b, difficultyCode, direction) {
  const aLevel = chartLevelValue(chartByDifficulty(a, difficultyCode));
  const bLevel = chartLevelValue(chartByDifficulty(b, difficultyCode));
  if (aLevel === null && bLevel === null) {
    return compareSongsByTitle(a, b);
  }
  if (aLevel === null) {
    return 1;
  }
  if (bLevel === null) {
    return -1;
  }
  if (aLevel !== bLevel) {
    return direction === "desc" ? bLevel - aLevel : aLevel - bLevel;
  }
  return compareSongsByTitle(a, b);
}

function sortSongsForDisplay(songs) {
  const sorted = [...songs];
  const direction = state.sortDirection === "desc" ? -1 : 1;
  if (state.sortKey === "title") {
    return sorted.sort((a, b) => direction * compareSongsByTitle(a, b));
  }
  if (state.sortKey === "artist") {
    return sorted.sort((a, b) => direction * compareSongsByArtist(a, b));
  }
  if (DIFFICULTY_COLUMNS.some((column) => column.key === state.sortKey)) {
    return sorted.sort((a, b) => compareSongsByLevel(a, b, state.sortKey, state.sortDirection));
  }
  return sorted.sort(compareSongsByTitle);
}

function setSort(key) {
  if (state.sortKey === key) {
    state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
  } else {
    state.sortKey = key;
    state.sortDirection = "asc";
  }
  searchSongs();
}

function difficultyClass(chart) {
  return String(chart.difficulty_code).replace(/^[0-9]+/, "").toLowerCase();
}

function imageMeta(chart) {
  const size = chart.image_size || [0, 0];
  const duration = Number(chart.duration_sec || 0).toFixed(1);
  return `${chart.visible_note_count} notes / ${duration}s / ${size[0]} x ${size[1]}`;
}

function setPreviewCover(chart) {
  const coverUrl = chart.cover_url || "";
  elements.previewCoverFrame.classList.toggle("hidden", !coverUrl);
  if (!coverUrl) {
    elements.previewCover.removeAttribute("src");
    elements.previewCover.alt = "";
    return;
  }
  elements.previewCover.src = coverUrl;
  elements.previewCover.alt = `${chart.title || chart.basename} cover`;
}

function chartHash(chart) {
  return `#/chart/${encodeURIComponent(chart.basename)}/${encodeURIComponent(chart.difficulty_code)}`;
}

function parseChartHash() {
  const match = location.hash.match(/^#\/chart\/([^/]+)\/([^/]+)$/);
  if (!match) {
    return null;
  }
  return {
    basename: decodeURIComponent(match[1]),
    difficultyCode: decodeURIComponent(match[2]),
  };
}

function updateIndexStatus() {
  if (!state.index) {
    elements.libraryStatus.textContent = "Index unavailable";
    return;
  }

  const completed = state.index.completed_count ?? state.index.exported_count ?? state.songs.length;
  const requested = state.index.requested_count ?? completed;
  const failures = state.index.failure_count ?? 0;
  elements.libraryStatus.textContent = `${state.songs.length} songs / ${completed} of ${requested} charts${failures ? ` / ${failures} failed` : ""}`;
}

function renderSongResults(items) {
  state.searchResults = items;
  elements.songResults.innerHTML = "";

  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "no-results";
    empty.textContent = "No indexed charts";
    elements.songResults.appendChild(empty);
    return;
  }

  const table = document.createElement("table");
  table.className = "song-table";
  table.dataset.sortKey = state.sortKey;
  table.dataset.sortDirection = state.sortDirection;

  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  const headers = [
    { key: "title", label: "Title", className: "title-column" },
    { key: "artist", label: "Artist", className: "artist-column" },
    ...DIFFICULTY_COLUMNS.map((column) => ({ key: column.key, label: column.label, className: `level-column ${difficultyClass({ difficulty_code: column.key })}` })),
  ];

  for (const header of headers) {
    const th = document.createElement("th");
    th.className = header.className;
    if (state.sortKey === header.key) {
      th.classList.add("sorted");
      th.dataset.direction = state.sortDirection;
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = "table-sort-button";
    button.dataset.sortKey = header.key;
    button.textContent = header.label;
    button.addEventListener("click", () => setSort(header.key));
    th.appendChild(button);
    headerRow.appendChild(th);
  }
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const song of items) {
    const row = document.createElement("tr");

    const titleCell = document.createElement("td");
    titleCell.className = "title-column";
    const title = document.createElement("strong");
    title.textContent = song.title;
    titleCell.appendChild(title);

    const artistCell = document.createElement("td");
    artistCell.className = "artist-column";
    if (state.sortKey === "artist") {
      artistCell.classList.add("sorted");
    }
    artistCell.textContent = song.artist || "";

    if (state.sortKey === "title") {
      titleCell.classList.add("sorted");
    }
    row.append(titleCell, artistCell);

    for (const column of DIFFICULTY_COLUMNS) {
      const chart = chartByDifficulty(song, column.key);
      const levelCell = document.createElement("td");
      levelCell.className = `level-column ${difficultyClass({ difficulty_code: column.key })}`;
      if (state.sortKey === column.key) {
        levelCell.classList.add("sorted");
      }
      const label = levelLabel(chart);
      if (chart && label) {
        const link = document.createElement("a");
        link.href = chartHash(chart);
        link.textContent = label;
        link.title = chartLabel(chart);
        levelCell.appendChild(link);
      }
      row.appendChild(levelCell);
    }

    tbody.appendChild(row);
  }
  table.appendChild(tbody);
  elements.songResults.appendChild(table);
}

function searchSongs() {
  const query = elements.searchInput.value.trim().toLocaleLowerCase();
  const filtered = state.songs.filter((song) => {
    if (!query) {
      return true;
    }
    return [song.title, song.artist, song.basename].some((value) => String(value || "").toLocaleLowerCase().includes(query));
  });
  const results = sortSongsForDisplay(filtered);

  renderSongResults(results);
  setStatus(`${results.length} song${results.length === 1 ? "" : "s"}`, "ok");
}

function setImageState(mode) {
  elements.emptyState.classList.toggle("hidden", mode !== "empty");
  elements.imageLoading.classList.toggle("hidden", mode !== "loading");
  elements.imageError.classList.toggle("hidden", mode !== "error");
  elements.chartImage.classList.toggle("ready", mode === "ready");
}

function findChart(basename, difficultyCode) {
  const song = state.songs.find((item) => item.basename === basename);
  if (!song) {
    return null;
  }
  const chart = song.difficulties.find((item) => item.difficulty_code === difficultyCode);
  return chart ? { song, chart } : null;
}

function showList() {
  setView("list");
  document.title = "NOSTALGIA 谱面目录 - 雪月";
  if (location.hash) {
    history.replaceState(null, "", location.pathname);
  }
  requestAnimationFrame(() => window.scrollTo(0, state.listScrollY));
}

function showChart(chart, { updateHash = true } = {}) {
  if (!chart) {
    return;
  }

  state.selectedDifficulty = chart;
  state.listScrollY = window.scrollY;
  setView("chart");
  window.scrollTo(0, 0);
  elements.imageStage.scrollTo({ top: 0, left: 0 });
  document.title = `${chart.title || chart.basename} - ${chartLabel(chart)}`;
  if (updateHash && location.hash !== chartHash(chart)) {
    history.replaceState(null, "", chartHash(chart));
  }

  elements.previewTitle.textContent = chart.title || chart.basename;
  elements.previewArtist.textContent = chart.artist || "Unknown artist";
  setPreviewCover(chart);
  const level = levelLabel(chart);
  elements.previewDifficulty.textContent = [chart.difficulty_name || "", level].filter(Boolean).join(" ");
  elements.previewDifficulty.className = `preview-chip ${difficultyClass(chart)}`;
  elements.previewMeta.textContent = imageMeta(chart);
  elements.chartImage.alt = `${chart.title || chart.basename} ${chartLabel(chart)}`;
  setImageState("loading");
  setStatus("");

  if (elements.chartImage.src.endsWith(chart.image_url)) {
    setImageState(elements.chartImage.complete && elements.chartImage.naturalWidth ? "ready" : "loading");
  } else {
    elements.chartImage.src = chart.image_url;
  }
}

function routeFromHash() {
  const route = parseChartHash();
  if (!route) {
    showList();
    return;
  }

  if (!state.songs.length) {
    setView("chart");
    setImageState("loading");
    return;
  }

  const found = findChart(route.basename, route.difficultyCode);
  if (!found) {
    showList();
    setStatus("Chart is not indexed yet", "error");
    return;
  }

  showChart(found.chart, { updateHash: false });
}

async function loadIndex() {
  setStatus("Loading index");

  try {
    state.index = await fetchPreferredIndex();
    state.songs = buildSongs(state.index.charts || []);
    updateIndexStatus();
    searchSongs();
    routeFromHash();
  } catch (error) {
    setStatus(error.message, "error");
    elements.libraryStatus.textContent = "Index unavailable";
  }
}

async function fetchPreferredIndex() {
  const indexUrls = ["/chart_index_chartonly_r2.json", "/chart_index_chartonly_webp.json", "/chart_index_chartonly.json", "/chart_index.json"];
  let lastError = null;
  for (const url of indexUrls) {
    const response = await fetch(`${url}?ts=${Date.now()}`, { cache: "no-store" });
    if (response.ok) {
      return response.json();
    }
    lastError = new Error(`Index request failed: ${response.status}`);
    if (response.status !== 404) {
      throw lastError;
    }
  }
  throw lastError || new Error("Index unavailable");
}

elements.searchButton.addEventListener("click", searchSongs);
elements.searchInput.addEventListener("input", searchSongs);
elements.searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    searchSongs();
  }
});
elements.listButton.addEventListener("click", showList);
elements.chartImage.addEventListener("load", () => {
  setImageState("ready");
});
elements.chartImage.addEventListener("error", () => {
  setImageState("error");
});
window.addEventListener("hashchange", routeFromHash);

setView("list");
setImageState("empty");
loadIndex();
