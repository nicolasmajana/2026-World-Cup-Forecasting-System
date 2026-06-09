// Map canonical team name -> flagcdn.com code (ISO 3166-1 alpha-2, lowercase;
// UK home nations use flagcdn's gb-eng / gb-sct / gb-wls / gb-nir).
// flagcdn is free, cached, and renders everywhere (unlike flag emoji on Windows).
const NAME_TO_FLAG: Record<string, string> = {
  Algeria: "dz", Argentina: "ar", Australia: "au", Austria: "at",
  Belgium: "be", Brazil: "br", Canada: "ca", "Cape Verde": "cv",
  Colombia: "co", Croatia: "hr", "Curaçao": "cw", Czechia: "cz",
  "DR Congo": "cd", Ecuador: "ec", Egypt: "eg", England: "gb-eng",
  France: "fr", Germany: "de", Ghana: "gh", Haiti: "ht",
  Iran: "ir", Iraq: "iq", "Ivory Coast": "ci", Japan: "jp",
  Jordan: "jo", Mexico: "mx", Morocco: "ma", Netherlands: "nl",
  "New Zealand": "nz", Norway: "no", Panama: "pa", Paraguay: "py",
  Portugal: "pt", Qatar: "qa", "Saudi Arabia": "sa", Scotland: "gb-sct",
  Senegal: "sn", "South Africa": "za", "South Korea": "kr", Spain: "es",
  Sweden: "se", Switzerland: "ch", Tunisia: "tn", Turkey: "tr",
  "United States": "us", Uruguay: "uy", Uzbekistan: "uz",
  "Bosnia and Herzegovina": "ba", "Bosnia & Herzegovina": "ba",
  Wales: "gb-wls", "Northern Ireland": "gb-nir", Italy: "it",
  Nigeria: "ng", Cameroon: "cm", Chile: "cl", Peru: "pe",
};

/** Returns a flagcdn URL for a team name, or null if unknown (e.g. TBD slots). */
export function flagUrl(teamName: string, width: 20 | 40 | 80 = 40): string | null {
  const code = NAME_TO_FLAG[teamName];
  return code ? `https://flagcdn.com/w${width}/${code}.png` : null;
}

/**
 * Most likely scoreline from expected goals. We round each side's expected
 * goals to the nearest whole number, which tracks the dominant scorelines
 * better than flooring (which always rounded down). Returns "2-1" style.
 */
export function predictedScore(
  xgHome: string | null,
  xgAway: string | null,
): string | null {
  if (xgHome == null || xgAway == null) return null;
  return `${Math.round(parseFloat(xgHome))}-${Math.round(parseFloat(xgAway))}`;
}
