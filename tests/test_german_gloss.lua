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

local function mock_env(dict_value, name_space)
  return {
    name_space = name_space or "*german_gloss",
    engine = { schema = { config = {
      get_string = function(_, key)
        if dict_value and key == ((name_space or "german_gloss"):gsub("^%*", "")) .. "/dictionary" then
          return dict_value
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

print(string.format("%d/%d checks passed", total - failures, total))
os.exit(failures == 0 and 0 or 1)
