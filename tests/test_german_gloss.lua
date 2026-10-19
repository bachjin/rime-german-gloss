-- Offline unit tests for lua/german_gloss.lua with mocked librime-lua objects.
-- Run from the repository root:  lua tests/test_german_gloss.lua
-- Mocks reproduce librime-lua semantics verified against its src/types.cc:
-- setting `comment` is honoured only for Phrase/Sentence/Simple candidates
-- and is a silent no-op for Shadow/Uniquified candidates.

package.path = "./lua/?.lua;" .. package.path

local REPO = "."

-- ---- mocks ---------------------------------------------------------------
local function Candidate(dyn, text, comment)
  local raw = { _dyn = dyn, text = text, type = "mock", _comment = comment or "" }
  return setmetatable({}, {
    __index = function(_, k)
      if k == "comment" then return raw._comment end
      return raw[k]
    end,
    __newindex = function(_, k, v)
      if k == "comment" then
        if raw._dyn == "Phrase" or raw._dyn == "Sentence" or raw._dyn == "Simple" then
          raw._comment = v
        end
      else
        raw[k] = v
      end
    end,
  })
end

function ShadowCandidate(item, typ, text, comment)
  local c = Candidate("Shadow", text ~= "" and text or item.text, comment)
  c.type = typ
  c.item = item
  return c
end

rime_api = {
  get_user_data_dir = function() return REPO end,
  get_shared_data_dir = function() return REPO .. "/nonexistent-shared" end,
}

local warnings = {}
log = { warning = function(m) warnings[#warnings + 1] = m end }

local function make_input(list)
  return { iter = function()
    local i = 0
    return function() i = i + 1; return list[i] end
  end }
end

local function run_filter(gloss, env, cands)
  local out = {}
  yield = function(c) out[#out + 1] = c end
  gloss.func(make_input(cands), env)
  return out
end

local function mock_env(dict_value, name_space, extra)
  return {
    name_space = name_space or "*german_gloss",
    engine = { schema = { config = {
      get_string = function(_, key)
        if dict_value and key == ((name_space or "german_gloss"):gsub("^%*", "")) .. "/dictionary" then
          return dict_value
        end
        if key:match("/base_dictionary$") then
          return (extra and extra.base_dictionary) or "none"
        end
        if extra then
          local short = key:match("/(.+)$")
          return extra[short]
        end
        return nil
      end,
    } } },
  }
end

-- ---- tests ---------------------------------------------------------------
local gloss = require("german_gloss")
local failures, total = 0, 0
local function check(name, cond)
  total = total + 1
  if not cond then
    failures = failures + 1
    print("FAIL: " .. name)
  end
end

-- 1. default dictionary loads and contains the four required entries
local env = mock_env(nil)
gloss.init(env)
check("dict 学校", env.gloss_dict["学校"] == "die Schule")
check("dict 工作", env.gloss_dict["工作"] == "die Arbeit")
check("dict 研究", env.gloss_dict["研究"] == "die Forschung")
check("dict 电脑", env.gloss_dict["电脑"] == "der Computer")

-- 2. filter behaviour
local out = run_filter(gloss, env, {
  Candidate("Phrase", "学校", ""),            -- hit, no comment
  Candidate("Phrase", "工作", "〔繁〕"),       -- hit, existing comment preserved
  Candidate("Shadow", "研究", "〔研究〕"),     -- hit, comment not settable -> wrapped
  Candidate("Phrase", "学", ""),              -- miss, untouched
  Candidate("Sentence", "电脑", "~dn"),       -- hit, sentence candidate
})
check("count preserved", #out == 5)
check("no comment -> leading space", out[1].comment == " die Schule")
check("existing comment kept + appended", out[2].comment == "〔繁〕 die Arbeit")
check("shadow wrapped", out[3].comment == "〔研究〕 die Forschung" and out[3].text == "研究")
check("shadow type kept", out[3].type == "mock")
check("miss untouched", out[4].comment == "" and out[4].text == "学")
check("sentence appended", out[5].comment == "~dn der Computer")
check("order preserved", out[1].text == "学校" and out[4].text == "学" and out[5].text == "电脑")

-- 3. parser: BOM, CRLF, comments, blank lines, duplicates, malformed lines
local tmp = os.tmpname()
local f = assert(io.open(tmp, "wb"))
f:write("\239\187\191学校\tdie Schule\r\n# comment\r\n\r\n学校\tdie Hochschule\r\n学校\tdie Schule\r\nkein tab\r\n 银行 \t die Bank \r\n")
f:close()
local fh = assert(io.open(tmp, "r"))
local d = gloss.parse(fh)
fh:close()
check("BOM stripped + dup joined", d["学校"] == "die Schule; die Hochschule")
check("malformed ignored", d["kein tab"] == nil)
check("trimmed", d["银行"] == "die Bank")

-- 4. configured absolute dictionary path
gloss.clear_cache()
local env2 = mock_env(tmp, "*german_gloss")
gloss.init(env2)
check("absolute dictionary config", env2.gloss_dict["银行"] == "die Bank")
os.remove(tmp)

-- 5. custom name space via lua_filter@*german_gloss@de_gloss
local env3 = mock_env("german_gloss/zh_de.tsv", "de_gloss")
gloss.init(env3)
check("custom name space", env3.gloss_dict["电脑"] == "der Computer")

-- 6. missing dictionary: empty table, warning logged, candidates pass through
local env4 = mock_env("does/not/exist.tsv")
gloss.init(env4)
check("missing dict empty", next(env4.gloss_dict) == nil)
check("missing dict warned", #warnings == 1)
local out4 = run_filter(gloss, env4, { Candidate("Phrase", "学校", "") })
check("missing dict passthrough", out4[1].comment == "")


-- 7. script normalization with a mocked OpenCC t2s converter
local T2S = { ["學"] = "学", ["電"] = "电", ["腦"] = "脑", ["銀"] = "银" }
local opencc_calls = {}
Opencc = function(name)
  opencc_calls[#opencc_calls + 1] = name
  if name ~= "t2s.json" then return nil end  -- librime-lua returns nil when not found
  return { convert = function(_, text)
    return (text:gsub("[\192-\255][\128-\191]*", function(ch) return T2S[ch] or ch end))
  end }
end

gloss.clear_cache()
local env5 = mock_env(nil)
gloss.init(env5)
check("default opencc config", opencc_calls[1] == "t2s.json" and env5.gloss_conv ~= nil)
local out5 = run_filter(gloss, env5, {
  Candidate("Phrase", "學校", "～月"),   -- Traditional output (cangjie5, 漢字 mode)
  Candidate("Phrase", "電腦", ""),
  Candidate("Shadow", "学校", "〔學校〕"), -- simplifier output (汉字 mode, tips: all)
  Candidate("Phrase", "學", ""),         -- miss after normalization
})
check("traditional cand hits", out5[1].comment == "～月 die Schule")
check("traditional cand hits 2", out5[2].comment == " der Computer")
check("simplified shadow hits", out5[3].comment == "〔學校〕 die Schule")
check("normalized miss untouched", out5[4].comment == "")

-- traditional keys in the TSV; exact match takes precedence over normalization
local tmp2 = os.tmpname()
f = assert(io.open(tmp2, "wb"))
f:write("銀行\tdie Bank\n學校\tdie Schule (trad)\n学校\tdie Schule\n")
f:close()
gloss.clear_cache()
local env6 = mock_env(tmp2)
gloss.init(env6)
os.remove(tmp2)
check("traditional key aliased", gloss.lookup(env6.gloss_dict, env6.gloss_conv, "银行") == "die Bank")
check("traditional key exact", gloss.lookup(env6.gloss_dict, env6.gloss_conv, "銀行") == "die Bank")
check("exact precedence trad", gloss.lookup(env6.gloss_dict, env6.gloss_conv, "學校") == "die Schule (trad)")
check("existing simplified key kept", gloss.lookup(env6.gloss_dict, env6.gloss_conv, "学校") == "die Schule")

-- opencc_config: none disables; unknown config warns and disables
local env7 = mock_env(nil, nil, { opencc_config = "none" })
gloss.init(env7)
check("opencc none disables", env7.gloss_conv == nil
  and gloss.lookup(env7.gloss_dict, env7.gloss_conv, "學校") == nil)
local nwarn = #warnings
local env8 = mock_env(nil, nil, { opencc_config = "missing.json" })
gloss.init(env8)
check("missing opencc config disables", env8.gloss_conv == nil and #warnings == nwarn + 1)
Opencc = nil

-- 8. base dictionary: user entries override it, missing file is silent,
--    long glosses are truncated, dictionaries are loaded once
gloss.clear_cache()
local tmp3 = os.tmpname()
f = assert(io.open(tmp3, "wb"))
f:write("学校\tSchule (S, Edu)\n學校\tSchule (S, Edu)\n我\tich (Pron); wir; unsere (Pron); selbst (Pron)\n")
f:close()
local env9 = mock_env(nil, nil, { base_dictionary = tmp3, max_length = "12" })
gloss.init(env9)
local out9 = run_filter(gloss, env9, {
  Candidate("Phrase", "学校", ""),   -- in both: user dictionary wins
  Candidate("Phrase", "學校", ""),   -- base only (no OpenCC here)
  Candidate("Phrase", "我", ""),     -- base only, truncated
  Candidate("Phrase", "你", ""),     -- miss
})
check("user dict overrides base", out9[1].comment == " die Schule")
check("base dict hit", out9[2].comment == " Schule (S, E…")
check("gloss truncated on char boundary", out9[3].comment == " ich (Pron)…")
check("base miss untouched", out9[4].comment == "")
os.remove(tmp3)
local env10 = mock_env(nil, nil, { base_dictionary = tmp3, max_length = "0" })
gloss.init(env10)
check("dictionary cached", env10.gloss_base == env9.gloss_base and env10.gloss_base["我"] ~= nil)
check("max_length 0 unlimited",
  run_filter(gloss, env10, { Candidate("Phrase", "我", "") })[1].comment
    == " ich (Pron); wir; unsere (Pron); selbst (Pron)")
nwarn = #warnings
gloss.clear_cache()
local env11 = mock_env(nil, nil, { base_dictionary = tmp3 })
gloss.init(env11)
check("missing base dict silent", #warnings == nwarn and next(env11.gloss_base) == nil)
check("utf8 truncate", gloss.truncate("für Äpfel", 5) == "für Ä…" and gloss.truncate("kurz", 5) == "kurz")

-- 8b. sorted dictionaries ("# sorted" header) are searched as one string
local sorted_text = "# generated\n# sorted\n" ..
  "Haus\tdas · 房子\nHause\tHaus 的变格\nHäuser\tHaus 的复数\nStraße\tdie · 路\n" ..
  "essen\t动 · 吃\nfür\t介 · 为了\ngehen\t动 · 走\r\nmüde\t形 · 累\nzu\t\n"
local sd = gloss.sorted_dict(sorted_text)
check("sorted: first", sd["Haus"] == "das · 房子")
check("sorted: prefix is another key", sd["Hause"] == "Haus 的变格")
check("sorted: non-ASCII", sd["Häuser"] == "Haus 的复数" and sd["für"] == "介 · 为了" and sd["müde"] == "形 · 累")
check("sorted: CRLF stripped", sd["gehen"] == "动 · 走")
check("sorted: middle", sd["essen"] == "动 · 吃" and sd["Straße"] == "die · 路")
check("sorted: misses", sd["Hau"] == nil and sd["haus"] == nil and sd["zzz"] == nil
  and sd["A"] == nil and sd["Häus"] == nil and sd[""] == nil and sd["a\tb"] == nil)
check("sorted: empty gloss is a miss", sd["zu"] == nil)
check("sorted: header is not a key", sd["# sorted"] == nil and sd["# generated"] == nil)
check("sorted: single line", gloss.sorted_dict("a\tx")["a"] == "x" and gloss.sorted_dict("a\tx")["b"] == nil)
check("sorted: empty", gloss.sorted_dict("# sorted\n")["a"] == nil)
local all_found = true
for line in sorted_text:gmatch("([^\n]+)\n") do
  local k, v = line:match("^([^#\t][^\t]*)\t(.+)$")
  if k and sd[k] ~= (v:gsub("\r$", "")) then all_found = false end
end
check("sorted: every key found", all_found)

gloss.clear_cache()
local tmp5 = os.tmpname()
f = assert(io.open(tmp5, "wb"))
f:write("\239\187\191" .. sorted_text)
f:close()
local loaded = gloss.load(tmp5)
check("load: marker gives a sorted dict", getmetatable(loaded) ~= nil and loaded["müde"] == "形 · 累")
local env12 = mock_env(nil, "*german_gloss@de_zh", { base_dictionary = tmp5, opencc_config = "none" })
gloss.init(env12)
local out12 = run_filter(gloss, env12, { Candidate("Phrase", "Häuser", ""), Candidate("Phrase", "xyz", "") })
check("filter with sorted base", out12[1].comment == " Haus 的复数" and out12[2].comment == "")
os.remove(tmp5)
local tmp6 = os.tmpname()
f = assert(io.open(tmp6, "wb"))
f:write("# not sorted\nb\tB\na\tA\n")
f:close()
local unsorted = gloss.load(tmp6)
check("load: no marker gives a table", getmetatable(unsorted) == nil and unsorted.a == "A" and unsorted.b == "B")
os.remove(tmp6)

-- 9. split input: the word formed with the preceding segments comes first
gloss.clear_cache()
local tmp4 = os.tmpname()
f = assert(io.open(tmp4, "wb"))
f:write("约\tVerabredung\n束\tbinden\n约束\tzügeln (V)\n不受约束\tungebunden (Adj)\n")
f:close()
local function Segment(start, stop, text)
  return { start = start, _end = stop,
           get_selected_candidate = function() return text and { text = text } or nil end }
end
-- `list` mocks the composition; `via_get_at` hides get_segments, as on an older librime-lua
local function split_env(list, via_get_at)
  local env = mock_env(tmp4)
  gloss.init(env)
  local segmentation = {
    get_at = function(_, i) return list[i + 1] end,
  }
  if not via_get_at then
    segmentation.get_segments = function() return list end
  end
  env.engine.context = { composition = { toSegmentation = function() return segmentation end } }
  return env
end
local function filter_last(env, list, cands)
  gloss.tags_match(list[#list], env)
  return run_filter(gloss, env, cands)
end

local split = { Segment(0, 5, "约"), Segment(5, 7) }
local env13 = split_env(split)
local out13 = filter_last(env13, split, { Candidate("Phrase", "束", ""), Candidate("Phrase", "棣", "") })
check("tags_match applies everywhere", gloss.tags_match(split[2], env13) == true)
check("word with preceding segment", out13[1].comment == " 约束: zügeln (V)")
check("no word: candidate's own gloss", out13[2].comment == "")
check("first segment has nothing before it",
  filter_last(env13, { split[1] }, { Candidate("Phrase", "约", "") })[1].comment == " Verabredung")

local long = { Segment(0, 2, "不"), Segment(2, 5, "受"), Segment(5, 9, "约"), Segment(9, 11) }
local env14 = split_env(long, true)
gloss.tags_match(long[#long], env14)
check("preceding texts in order, via get_at", table.concat(gloss.preceding_texts(env14), "|") == "不|受|约")
check("longest word first",
  filter_last(env14, long, { Candidate("Phrase", "束", "") })[1].comment == " 不受约束: ungebunden (Adj)")

local gap = { Segment(0, 3, "约"), Segment(4, 6) }   -- not adjacent: nothing before
local env15 = split_env(gap)
check("non-adjacent segment ignored",
  filter_last(env15, gap, { Candidate("Phrase", "束", "") })[1].comment == " binden")
local env16 = mock_env(tmp4)                         -- no context at all
gloss.init(env16)
gloss.tags_match(Segment(5, 7), env16)
check("missing context: plain gloss",
  run_filter(gloss, env16, { Candidate("Phrase", "束", "") })[1].comment == " binden")
os.remove(tmp4)

-- a failing lookup passes the candidate through
local env12 = mock_env(nil)
gloss.init(env12)
env12.gloss_conv = { convert = function() error("boom") end }
check("lookup error passthrough",
  run_filter(gloss, env12, { Candidate("Phrase", "學", "x") })[1].comment == "x")

print(string.format("%d/%d checks passed", total - failures, total))
os.exit(failures == 0 and 0 or 1)
