-- Offline unit tests for lua/typeduck_gloss.lua with mocked librime-lua objects.
-- Run from the repository root:  lua tests/test_typeduck_gloss.lua

package.path = "./lua/?.lua;" .. package.path

local US, RS = "\31", "\30"
local function record(...) return table.concat({ ... }, US) end

-- ---- fixture: a user data directory holding lua/typeduck_gloss.txt ---------
local dir = os.tmpname()
os.remove(dir)
assert(os.execute('mkdir -p "' .. dir .. '/lua"'))
local index_path = dir .. "/lua/typeduck_gloss.txt"
local f = assert(io.open(index_path, "wb"))
f:write("行\t" .. table.concat({
  record("haang4", "v", "walk", "पैदल चलना", "چلنا", "", ""),
  record("hong2", "n", "bank", "", "", "", ""),
  record("hong4", "mw", "row, profession", "व्यवसाय", "شعبہ", "", ""),
}, RS) .. "\n")
f:write("香港\t" .. record("hoeng1gong2", "n", "Hong Kong", "", "", "", "") .. "\n")
f:write("唔該\t" .. record("m4goi1", "", "thank you", "", "", "", "terima kasih") .. "\n")
f:write("印\t" .. record("jan3", "n", "", "छाप", "", "", "") .. "\n")
f:write("no tab on this line\n")
f:close()

-- ---- mocks ---------------------------------------------------------------
local function Candidate(text, comment, preedit)
  return { text = text, comment = comment, preedit = preedit or "", type = "mock" }
end

function ShadowCandidate(item, typ, text, comment)
  return { text = text, comment = comment, type = typ, item = item, shadow = true }
end

rime_api = {
  get_user_data_dir = function() return dir end,
  get_shared_data_dir = function() return dir .. "/nonexistent-shared" end,
}

local warnings = {}
log = { warning = function(m) warnings[#warnings + 1] = m end }

-- `values` maps "typeduck_gloss/<key>" suffixes to config values; a `false`
-- accessor name in `broken` makes that accessor raise, as on an older librime-lua.
local function mock_env(values, name_space, broken)
  values, broken = values or {}, broken or {}
  local function getter(name)
    return function(_, key)
      if broken[name] then error(name .. " unsupported") end
      return values[key:match("/(.+)$")]
    end
  end
  return {
    name_space = name_space or "*typeduck_gloss",
    engine = { schema = { config = {
      get_bool = getter("get_bool"),
      get_string = getter("get_string"),
      get_int = getter("get_int"),
      get_list = function(_, key)
        if broken.get_list then error("get_list unsupported") end
        local list = values[key:match("/(.+)$")]
        if not list then return nil end
        return {
          size = #list,
          get_value_at = function(_, i)
            return { get_string = function() return list[i + 1] end }
          end,
        }
      end,
    } } },
  }
end

local function run_filter(gloss, env, cands)
  local out = {}
  yield = function(c) out[#out + 1] = c end
  gloss.func({ iter = function()
    local i = 0
    return function() i = i + 1; return cands[i] end
  end }, env)
  return out
end

-- ---- tests ---------------------------------------------------------------
local gloss = require("typeduck_gloss")
local failures, total = 0, 0
local function check(name, cond)
  total = total + 1
  if not cond then
    failures = failures + 1
    print("FAIL: " .. name)
  end
end

-- 1. defaults: English only, no part of speech, comment kept in front
local env = mock_env()
gloss.init(env)
check("default language", #env.langs == 1 and env.langs[1] == "eng")
check("default separator and length", env.separator == " / " and env.max_length == 60)
check("malformed index line ignored", env.index["no tab on this line"] == nil)
local out = run_filter(gloss, env, {
  Candidate("香港", "hoeng1 gong2"),
  Candidate("行", "hong4"),
  Candidate("行", "hong2"),
  Candidate("行", "haang4"),
  Candidate("香", "hoeng1"),          -- not in the index
  Candidate("印", "jan3"),            -- in the index, but no English gloss
  Candidate("唔該", ""),              -- no comment at all
})
check("count preserved", #out == 7)
check("comment kept, gloss appended", out[1].comment == "hoeng1 gong2  Hong Kong")
check("wrapped in a shadow candidate", out[1].shadow and out[1].text == "香港" and out[1].type == "mock")
check("hong4 picks row", out[2].comment == "hong4  row, profession")
check("hong2 picks bank", out[3].comment == "hong2  bank")
check("haang4 picks walk", out[4].comment == "haang4  walk")
check("miss untouched", out[5].shadow == nil and out[5].comment == "hoeng1")
check("no gloss in chosen language untouched", out[6].shadow == nil and out[6].comment == "jan3")
check("empty comment -> gloss alone", out[7].comment == "thank you")

-- 2. no spelling hints: fall back to the typed code, tones optional
out = run_filter(gloss, env, {
  Candidate("行", "", "hong4"),
  Candidate("行", "", "hong"),        -- toneless: first record spelled "hong"
  Candidate("行", "", "zzz"),         -- no match: first record
  Candidate("行", nil, nil),          -- nothing to go on: first record
})
check("preedit with tone", out[1].comment == "row, profession")
check("toneless preedit takes first same spelling", out[2].comment == "bank")
check("unmatched preedit takes first record", out[3].comment == "walk")
check("nil comment and preedit", out[4].comment == "walk")

-- 3. configuration: languages, part of speech, separator, truncation
local env2 = mock_env({ languages = { "eng", "hin", "urd", "xxx" }, show_pos = true, separator = " | ", max_length = 0 })
gloss.init(env2)
out = run_filter(gloss, env2, { Candidate("行", "hong4"), Candidate("唔該", "m4 goi1"), Candidate("印", "jan3") })
check("several languages + pos", out[1].comment == "hong4  (mw) row, profession | व्यवसाय | شعبہ")
check("empty languages and empty pos skipped", out[2].comment == "m4 goi1  thank you")
check("language without English", out[3].comment == "jan3  (n) छाप")

local env3 = mock_env({ max_length = 6, show_pos = true })
gloss.init(env3)
out = run_filter(gloss, env3, { Candidate("行", "hong4"), Candidate("行", "hong2") })
check("truncated by characters, pos not counted", out[1].comment == "hong4  (mw) row, p…")
check("short gloss not truncated", out[2].comment == "hong2  (n) bank")
check("truncate counts UTF-8 characters", gloss.truncate("व्यवसाय", 3) == "व्य…")

-- 4. custom name space, and accessors missing from librime-lua
local env4 = mock_env({ languages = { "ind" } }, "yue_gloss")
gloss.init(env4)
out = run_filter(gloss, env4, { Candidate("唔該", "m4 goi1") })
check("custom name space", out[1].comment == "m4 goi1  terima kasih")

local env5 = mock_env({ languages = { "hin" }, max_length = 3 }, nil, { get_list = true, get_int = true, get_bool = true })
check("init survives missing accessors", pcall(gloss.init, env5))
check("defaults when accessors fail", env5.langs[1] == "eng" and env5.max_length == 60 and not env5.show_pos)

-- 5. helpers
check("normalize", gloss.normalize("hoeng1 gong2") == "hoeng1gong2" and gloss.normalize(nil) == "")
check("split keeps empty fields", #gloss.split("a" .. US .. US .. "c", US) == 3)
check("pick_record single", gloss.pick_record(record("x1", "n", "only"), "y2")[3] == "only")

-- 6. missing index: warn once per load, pass candidates through
os.remove(index_path)
gloss.clear_cache()
local env6 = mock_env()
gloss.init(env6)
check("missing index warns", #warnings == 1 and warnings[1]:find("index not found", 1, true) ~= nil)
out = run_filter(gloss, env6, { Candidate("香港", "hoeng1 gong2") })
check("missing index passes through", #out == 1 and out[1].shadow == nil)

os.execute('rm -rf "' .. dir .. '"')
print(string.format("%d/%d checks passed", total - failures, total))
os.exit(failures == 0 and 0 or 1)
