const state = {
  index: null,
  songs: [],
  selectedSong: null,
  selectedDifficulty: null,
  searchResults: [],
};

const elements = {
  libraryStatus: document.querySelector("#libraryStatus"),
  refreshButton: document.querySelector("#refreshButton"),
  searchInput: document.querySelector("#searchInput"),
  searchButton: document.querySelector("#searchButton"),
  songResults: document.querySelector("#songResults"),
  selectedTitle: document.querySelector("#selectedTitle"),
  selectedArtist: document.querySelector("#selectedArtist"),
  difficultyButtons: document.querySelector("#difficultyButtons"),
  statusText: document.querySelector("#statusText"),
  previewTitle: document.querySelector("#previewTitle"),
  previewMeta: document.querySelector("#previewMeta"),
  openImageLink: document.querySelector("#openImageLink"),
  chartImage: document.querySelector("#chartImage"),
  emptyState: document.querySelector("#emptyState"),
};

function setStatus(text, kind = "") {
  elements.statusText.textContent = text;
  elements.statusText.className = `status-text ${kind}`.trim();
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

function imageMeta(chart) {
  const size = chart.image_size || [0, 0];
  const duration = Number(chart.duration_sec || 0).toFixed(1);
  return `${chart.visible_note_count} notes / ${duration}s / ${size[0]} x ${size[1]}`;
}

function updateIndexStatus() {
  if (!state.index) {
    elements.libraryStatus.textContent = "Index unavailable";
    return;
  }

  const completed = state.index.completed_count ?? state.index.exported_count ?? state.songs.length;
  const requested = state.index.requested_count ?? completed;
  const failures = state.index.failure_count ?? 0;
  elements.libraryStatus.textContent = `${completed} / ${requested} charts indexed${failures ? ` / ${failures} failed` : ""}`;
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

  for (const song of items) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "song-result";
    if (state.selectedSong?.basename === song.basename) {
      button.classList.add("active");
    }

    button.innerHTML = "<strong></strong><span></span><span></span>";
    button.querySelector("strong").textContent = song.title;
    const spans = button.querySelectorAll("span");
    spans[0].textContent = song.artist || song.basename;
    spans[1].textContent = song.difficulties.map(chartLabel).join(" / ");
    button.addEventListener("click", () => selectSong(song));
    elements.songResults.appendChild(button);
  }
}

function searchSongs() {
  const query = elements.searchInput.value.trim().toLocaleLowerCase();
  const results = state.songs.filter((song) => {
    if (!query) {
      return true;
    }
    return [song.title, song.artist, song.basename].some((value) => String(value || "").toLocaleLowerCase().includes(query));
  });

  renderSongResults(results.slice(0, 60));
  setStatus(`${results.length} result${results.length === 1 ? "" : "s"}`, "ok");
}

function renderDifficultyButtons() {
  elements.difficultyButtons.innerHTML = "";
  if (!state.selectedSong) {
    return;
  }

  for (const difficulty of state.selectedSong.difficulties) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = chartLabel(difficulty);
    if (state.selectedDifficulty?.difficulty_code === difficulty.difficulty_code) {
      button.classList.add("active");
    }
    button.addEventListener("click", () => showChart(difficulty));
    elements.difficultyButtons.appendChild(button);
  }
}

function selectSong(song) {
  state.selectedSong = song;
  elements.selectedTitle.textContent = song.title;
  elements.selectedArtist.textContent = song.artist || song.basename;
  renderSongResults(state.searchResults);
  renderDifficultyButtons();
  showChart(song.difficulties[song.difficulties.length - 1]);
}

function showChart(chart) {
  if (!chart) {
    return;
  }

  state.selectedDifficulty = chart;
  renderDifficultyButtons();

  elements.previewTitle.textContent = `${chart.title || chart.basename} - ${chartLabel(chart)}`;
  elements.previewMeta.textContent = imageMeta(chart);
  elements.chartImage.src = chart.image_url;
  elements.chartImage.alt = `${chart.title || chart.basename} ${chartLabel(chart)}`;
  elements.chartImage.classList.add("ready");
  elements.emptyState.classList.add("hidden");
  elements.openImageLink.href = chart.image_url;
  elements.openImageLink.setAttribute("aria-disabled", "false");
  setStatus(`Loaded ${chartLabel(chart)}`, "ok");
}

async function loadIndex({ preserveSelection = false } = {}) {
  elements.refreshButton.disabled = true;
  setStatus("Loading index");

  try {
    const response = await fetch(`/chart_index_chartonly.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Index request failed: ${response.status}`);
    }

    state.index = await response.json();
    state.songs = buildSongs(state.index.charts || []);
    updateIndexStatus();

    const previousBasename = preserveSelection ? state.selectedSong?.basename : null;
    const previousDifficulty = preserveSelection ? state.selectedDifficulty?.difficulty_code : null;
    searchSongs();

    if (previousBasename) {
      const song = state.songs.find((item) => item.basename === previousBasename);
      if (song) {
        state.selectedSong = song;
        const difficulty = song.difficulties.find((item) => item.difficulty_code === previousDifficulty) || song.difficulties[song.difficulties.length - 1];
        elements.selectedTitle.textContent = song.title;
        elements.selectedArtist.textContent = song.artist || song.basename;
        renderSongResults(state.searchResults);
        renderDifficultyButtons();
        showChart(difficulty);
      }
    }
  } catch (error) {
    setStatus(error.message, "error");
    elements.libraryStatus.textContent = "Index unavailable";
  } finally {
    elements.refreshButton.disabled = false;
  }
}

elements.searchButton.addEventListener("click", searchSongs);
elements.searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    searchSongs();
  }
});
elements.refreshButton.addEventListener("click", () => loadIndex({ preserveSelection: true }));

loadIndex();
