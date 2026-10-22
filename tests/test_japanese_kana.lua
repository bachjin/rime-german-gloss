-- Offline unit tests for lua/japanese_kana.lua with mocked librime-lua
-- objects. Run from the repository root:
--   lua tests/test_japanese_kana.lua

package.path = "./lua/?.lua;" .. package.path

local kana = require("japanese_kana")
local failures, total = 0, 0
local function check(name, cond)
  total = total + 1
  if not cond then
    failures = failures + 1
    print("FAIL: " .. name)
  end
end
local function eq(name, got, want)
  check(name .. " (got " .. tostring(got) .. ")", got == want)
end

-- 1. Romaji to hiragana
eq("plain", kana.to_hiragana("tsukue"), "つくえ")
eq("sokuon", kana.to_hiragana("gakkou"), "がっこう")
eq("tch", kana.to_hiragana("matcha"), "まっちゃ")
eq("n before consonant", kana.to_hiragana("shinbun"), "しんぶん")
eq("nn before vowel", kana.to_hiragana("konnichiha"), "こんにちは")
eq("n apostrophe", kana.to_hiragana("kin'en"), "きんえん")
eq("final nn", kana.to_hiragana("honn"), "ほん")
eq("final n", kana.to_hiragana("hon"), "ほん")
eq("kunrei", kana.to_hiragana("sitatu"), "したつ")
eq("yoon", kana.to_hiragana("nyuugaku"), "にゅうがく")
eq("ja / zya", kana.to_hiragana("jazya"), "じゃじゃ")
eq("foreign sounds", kana.to_hiragana("fairuthi"), "ふぁいるてぃ")
eq("long vowel", kana.to_hiragana("ko-hi-"), "こーひー")
eq("long vowel q", kana.to_hiragana("ko-hiq"), "こーひー")
eq("small kana", kana.to_hiragana("xa_ixtsulya"), "ぁぃっゃ")
eq("wo", kana.to_hiragana("wo"), "を")
eq("delimiter", kana.to_hiragana("ni hon"), "にほん")
eq("unknown kept", kana.to_hiragana("k"), "k")

-- 2. Katakana and half-width katakana
eq("katakana", kana.convert("konpyu-ta-", "katakana"), "コンピューター")
eq("vu", kana.convert("vaiorin", "katakana"), "ヴァイオリン")
eq("halfwidth", kana.convert("gakkou", "halfwidth"), "ｶﾞｯｺｳ")
eq("halfwidth p", kana.convert("pan", "halfwidth"), "ﾊﾟﾝ")
eq("halfwidth vu", kana.convert("vu", "halfwidth"), "ｳﾞ")
eq("hiragana mode", kana.convert("gakkou", "hiragana"), "がっこう")

-- 3. The processor
local function Engine(input, segments)
  local committed = {}
  local ctx = { input = input }
  function ctx:is_composing() return self.input ~= "" end
  function ctx:clear() self.input = "" end
  ctx.composition = { toSegmentation = function()
    return { get_segments = function() return segments or {} end }
  end }
  local engine = { context = ctx }
  function engine:commit_text(text) committed[#committed + 1] = text end
  return engine, committed
end

local function Key(repr)
  return { repr = function() return repr end }
end

local engine, committed = Engine("gakkou")
local env = { engine = engine }
check("F7 accepted", kana.func(Key("F7"), env) == 1)
eq("F7 commits katakana", committed[1], "ガッコウ")
check("input cleared", engine.context.input == "")
check("F7 idle: noop", kana.func(Key("F7"), env) == 2)

engine, committed = Engine("gakkou")
env = { engine = engine }
check("other key: noop", kana.func(Key("Shift+F6"), env) == 2 and kana.func(Key("a"), env) == 2)
check("nothing committed", #committed == 0)

-- a candidate chosen for the first segment is kept
local chosen = { status = "kSelected", _end = 5,
                 get_selected_candidate = function() return { text = "日本" } end }
local open = { status = "kGuess", _end = 9, get_selected_candidate = function() return nil end }
engine, committed = Engine("nihongo", { chosen, open })
env = { engine = engine }
kana.func(Key("F6"), env)
eq("chosen + rest", committed[1], "日本ご")

-- a broken composition falls back to the whole input
engine, committed = Engine("ne")
engine.context.composition = nil
kana.func(Key("F6"), { engine = engine })
eq("fallback", committed[1], "ね")

-- reverse lookup input is left alone
engine, committed = Engine("`ri")
check("reverse lookup: noop", kana.func(Key("F6"), { engine = engine }) == 2)

print(string.format("%d/%d checks passed", total - failures, total))
os.exit(failures == 0 and 0 or 1)
