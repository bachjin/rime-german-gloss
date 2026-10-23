-- japanese_kana.lua
-- librime-lua processor for the `japanese` schema (rime-japanese): while
-- composing, F6 commits the input converted to hiragana, F7 to katakana and
-- F8 to half-width katakana, like the keys of Microsoft IME:
--   gakkou F6 -> がっこう    gakkou F7 -> ガッコウ    gakkou F8 -> ｶﾞｯｺｳ
-- The conversion uses its own romaji table, not the dictionary, so any input
-- converts. Segments already chosen (a candidate selected for the first part
-- of the input) are committed as chosen, followed by the rest in kana.
--
-- Romaji: Hepburn and Kunrei (shi/si, chi/ti, tsu/tu, fu/hu, ja/zya …), a
-- doubled consonant for っ (kk, tch), n before a consonant or at the end, nn
-- or n' for ん, x / l / _ before a vowel for small kana (xa ぁ, xtsu っ), and
-- - or q for ー (the schema spells ー as -, typed q).
--
-- Usage in japanese.custom.yaml:
--   patch:
--     engine/processors/@before 0: lua_processor@*japanese_kana

local M = {}

local kAccepted = 1
local kNoop = 2

local KEYS = { F6 = "hiragana", F7 = "katakana", F8 = "halfwidth" }
local UTF8_CHAR = "[%z\1-\127\194-\244][\128-\191]*"

local function chars(s)
  local out = {}
  for ch in s:gmatch(UTF8_CHAR) do out[#out + 1] = ch end
  return out
end

-- ---- romaji table ----------------------------------------------------------

local TABLE = {}
local VOWELS = { "a", "i", "u", "e", "o" }

local ROWS = {
  [""] = "あいうえお", k = "かきくけこ", g = "がぎぐげご", s = "さしすせそ",
  z = "ざじずぜぞ", t = "たちつてと", d = "だぢづでど", n = "なにぬねの",
  h = "はひふへほ", b = "ばびぶべぼ", p = "ぱぴぷぺぽ", m = "まみむめも",
  r = "らりるれろ", x = "ぁぃぅぇぉ", l = "ぁぃぅぇぉ", _ = "ぁぃぅぇぉ",
}
for consonant, kana in pairs(ROWS) do
  local k = chars(kana)
  for i, v in ipairs(VOWELS) do TABLE[consonant .. v] = k[i] end
end

-- Rows whose kana are written with a small vowel or small y-kana.
local COMPOUND = {
  sh = { "しゃ", "し", "しゅ", "しぇ", "しょ" }, ch = { "ちゃ", "ち", "ちゅ", "ちぇ", "ちょ" },
  j = { "じゃ", "じ", "じゅ", "じぇ", "じょ" }, ts = { "つぁ", "つぃ", "つ", "つぇ", "つぉ" },
  f = { "ふぁ", "ふぃ", "ふ", "ふぇ", "ふぉ" }, v = { "ゔぁ", "ゔぃ", "ゔ", "ゔぇ", "ゔぉ" },
  th = { "てゃ", "てぃ", "てゅ", "てぇ", "てょ" }, dh = { "でゃ", "でぃ", "でゅ", "でぇ", "でょ" },
  w = { "わ", "うぃ", "う", "うぇ", "を" }, y = { "や", "い", "ゆ", "いぇ", "よ" },
  c = { "か", "し", "く", "せ", "こ" },
}
for consonant, kana in pairs(COMPOUND) do
  for i, v in ipairs(VOWELS) do TABLE[consonant .. v] = kana[i] end
end

-- ky, sy, ty …: the i-kana of the row plus a small ゃ ぃ ゅ ぇ ょ.
local SMALL_Y = { "ゃ", "ぃ", "ゅ", "ぇ", "ょ" }
local Y_ROWS = { k = "き", g = "ぎ", s = "し", z = "じ", t = "ち", c = "ち", d = "ぢ",
                 n = "に", h = "ひ", b = "び", p = "ぴ", m = "み", r = "り",
                 j = "じ", f = "ふ", v = "ゔ" }
for consonant, kana in pairs(Y_ROWS) do
  for i, v in ipairs(VOWELS) do TABLE[consonant .. "y" .. v] = kana .. SMALL_Y[i] end
end
for _, prefix in ipairs({ "x", "l", "_" }) do
  for i, v in ipairs(VOWELS) do TABLE[prefix .. "y" .. v] = SMALL_Y[i] end
  TABLE[prefix .. "tsu"] = "っ"
  TABLE[prefix .. "tu"] = "っ"
  TABLE[prefix .. "wa"] = "ゎ"
  TABLE[prefix .. "ka"] = "ゕ"
  TABLE[prefix .. "ke"] = "ゖ"
end
TABLE["twu"] = "とぅ"
TABLE["dwu"] = "どぅ"
TABLE["-"] = "ー"
TABLE["q"] = "ー"

local function is_vowel(c) return c ~= "" and ("aiueo"):find(c, 1, true) ~= nil end
local function is_letter(c) return c ~= "" and c:match("^[a-z]$") ~= nil end

-- `romaji` (lowercase input of the schema) in hiragana.
function M.to_hiragana(romaji)
  local s = romaji:lower()
  local out, i, n = {}, 1, #s
  while i <= n do
    local c = s:sub(i, i)
    local next = s:sub(i + 1, i + 1)
    if c == " " or c == "'" then
      i = i + 1
    elseif c == "n" and not is_vowel(next) and next ~= "y" then
      -- ん: n before a consonant or at the end; nn before a vowel is ん + na …
      out[#out + 1] = "ん"
      local after = s:sub(i + 2, i + 2)
      if (next == "n" and not is_vowel(after) and after ~= "y") or next == "'" then
        i = i + 2
      else
        i = i + 1
      end
    elseif is_letter(c) and not is_vowel(c) and (next == c or (c == "t" and s:sub(i + 1, i + 2) == "ch")) then
      out[#out + 1] = "っ"  -- kk, ss, tch …
      i = i + 1
    else
      local matched = false
      for len = 4, 1, -1 do
        local kana = TABLE[s:sub(i, i + len - 1)]
        if kana then
          out[#out + 1] = kana
          i = i + len
          matched = true
          break
        end
      end
      if not matched then
        out[#out + 1] = c
        i = i + 1
      end
    end
  end
  return table.concat(out)
end

-- ---- katakana --------------------------------------------------------------

-- Hiragana U+3041..U+3096 are katakana U+30A1..U+30F6 minus 0x60.
function M.to_katakana(hiragana)
  local out = {}
  for _, ch in ipairs(chars(hiragana)) do
    local code = utf8.codepoint(ch)
    if code >= 0x3041 and code <= 0x3096 then
      ch = utf8.char(code + 0x60)
    end
    out[#out + 1] = ch
  end
  return table.concat(out)
end

local HALF = {}
do
  local full = chars("ヲァィゥェォャュョッーアイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン")
  local half = chars("ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ")
  for i, ch in ipairs(full) do HALF[ch] = half[i] end
  local voiced = chars("ガギグゲゴザジズゼゾダヂヅデドバビブベボ")
  local base = chars("カキクケコサシスセソタチツテトハヒフヘホ")
  for i, ch in ipairs(voiced) do HALF[ch] = HALF[base[i]] .. "ﾞ" end
  local semi = chars("パピプペポ")
  for i, ch in ipairs(semi) do HALF[ch] = HALF[base[15 + i]] .. "ﾟ" end
  HALF["ヴ"] = "ｳﾞ"
  HALF["ヮ"] = "ﾜ"
  HALF["ヵ"] = "ｶ"
  HALF["ヶ"] = "ｹ"
end

function M.to_halfwidth(katakana)
  local out = {}
  for _, ch in ipairs(chars(katakana)) do out[#out + 1] = HALF[ch] or ch end
  return table.concat(out)
end

function M.convert(romaji, mode)
  local kana = M.to_hiragana(romaji)
  if mode == "hiragana" then return kana end
  kana = M.to_katakana(kana)
  if mode == "katakana" then return kana end
  return M.to_halfwidth(kana)
end

-- ---- processor -------------------------------------------------------------

-- The text of the segments chosen so far and where the rest of the input
-- starts; ("", 0) when nothing is chosen or the composition can't be read.
function M.chosen(context)
  local ok, text, pos = pcall(function()
    local text, pos = "", 0
    for _, seg in ipairs(context.composition:toSegmentation():get_segments()) do
      if seg.status ~= "kSelected" and seg.status ~= "kConfirmed" then break end
      local cand = seg:get_selected_candidate()
      if not cand then break end
      text, pos = text .. cand.text, seg._end
    end
    return text, pos
  end)
  if ok then return text, pos end
  return "", 0
end

function M.func(key, env)
  local mode = KEYS[key:repr()]
  if not mode then
    return kNoop
  end
  local context = env.engine.context
  if not context:is_composing() then
    return kNoop
  end
  local chosen, pos = M.chosen(context)
  local rest = context.input:sub(pos + 1)
  if rest:sub(1, 1) == "`" then
    return kNoop  -- a reverse lookup (`pinyin), not romaji
  end
  env.engine:commit_text(chosen .. M.convert(rest, mode))
  context:clear()
  return kAccepted
end

return M
