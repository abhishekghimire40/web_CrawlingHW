const DATA_FILE_URL = "data_by_business.json";

const featureContainer = document.getElementById("featured-container");
const reviewContainer = document.getElementById("reviews-container");
const businessSelect = document.getElementById("business-select");
const statusMessage = document.getElementById("status-message");
const errorMessage = document.getElementById("error-message");

let reviewsByBusiness = {};
let allReviews = [];

// helper functions
function formatStars(starNumber) {
  if (starNumber == null || Number.isNaN(starNumber)) return "";
  const rounded = Math.round(Number(starNumber) * 2) / 2; // step 0.5
  const full = "★".repeat(Math.floor(rounded));
  const half = rounded % 1 ? "½" : "";
  return full + half;
}

function createCard(innerHtml) {
  const article = document.createElement("article");
  article.className = "card";
  article.innerHTML = innerHtml;
  return article;
}

function renderFeaturedBusinesses(businessNames) {
  featureContainer.innerHTML = "";
  const firstThree = businessNames.slice(0, 3);
  firstThree.forEach((name) => {
    const firstReview =
      (reviewsByBusiness[name] && reviewsByBusiness[name][0]) || {};
    const city = firstReview.city || "St. Louis, MO";
    const ratingText =
      firstReview.stars != null ? `${firstReview.stars}★` : "—";

    featureContainer.appendChild(
      createCard(`
        <h3 class="card-title">${name}</h3>
        <p class="card-meta">${city} · ${ratingText}</p>
        <p class="card-text small-text">Popular with students. Quick bite, friendly staff.</p>
      `),
    );
  });
}

function flattenReviews() {
  const rows = [];
  Object.entries(reviewsByBusiness).forEach(([business, items]) => {
    (items || []).forEach((r) => rows.push({ business, ...r }));
  });
  // sort by newest first if dates are parseable else leave as it is
  rows.sort((a, b) => {
    const aTime = Date.parse(a.date || "");
    const bTime = Date.parse(b.date || "");
    if (!Number.isNaN(aTime) && !Number.isNaN(bTime)) return bTime - aTime;
    return 0;
  });
  return rows;
}

function renderReviewCards(reviews) {
  reviewContainer.innerHTML = "";
  reviews.forEach((r) => {
    const who = r.reviewer || "Anonymous";
    const when = r.date || "";
    const where = r.city ? ` · ${r.city}` : "";
    const stars = formatStars(r.stars);

    reviewContainer.appendChild(
      createCard(`
        <h3 class="card-title">${who} <span class="star-text">${stars}</span></h3>
        <p class="card-meta">${r.business}${where}${when ? " · " + when : ""}</p>
        <p class="card-text">${r.text || ""}</p>
      `),
    );
  });
}

function populateBusinessPicker(businessNames) {
  businessSelect.innerHTML = "";

  const optAll = document.createElement("option");
  optAll.value = "__all__";
  optAll.textContent = `All (${allReviews.length})`;
  businessSelect.appendChild(optAll);

  businessNames.forEach((name) => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = `${name} (${reviewsByBusiness[name]?.length || 0})`;
    businessSelect.appendChild(opt);
  });

  businessSelect.addEventListener("change", () => {
    const selected = businessSelect.value;
    if (selected === "__all__") {
      // show at least 5; up to 10 for variety
      renderReviewCards(allReviews.slice(0, 10));
    } else {
      const rows = (reviewsByBusiness[selected] || []).map((r) => ({
        business: selected,
        ...r,
      }));
      renderReviewCards(rows.slice(0, 10));
    }
  });
}

async function init() {
  try {
    const response = await fetch(DATA_FILE_URL, { cache: "no-store" });
    reviewsByBusiness = await response.json();

    const businessNames = Object.keys(reviewsByBusiness);
    renderFeaturedBusinesses(businessNames);

    allReviews = flattenReviews();
    populateBusinessPicker(businessNames);

    businessSelect.value = "__all__";
    renderReviewCards(allReviews.slice(0, 10));

    statusMessage.textContent = `Loaded ${allReviews.length} reviews.`;
  } catch (err) {
    console.error("Failed to load data:", err);
    errorMessage.hidden = false;
    statusMessage.textContent = "";
  }
}

init();
