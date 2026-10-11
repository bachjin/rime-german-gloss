-- typeduck_gloss.lua
-- librime-lua filter: append TypeDuck's multilingual gloss to the comments of
-- Cantonese (jyut6ping3) candidates.
--
-- Installed and enabled by install-jyutping.py, which also builds the index
-- this filter reads. It replaces TypeDuck's own dictionary_lookup_filter,
-- which needs TypeDuck's librime fork and emits a payload only TypeDuck's
-- frontends can render.
--
-- Usage in a schema, before `simplifier` (the index is keyed by the
-- Traditional text of the candidate):
--   engine/filters:
--     - lua_filter@*typeduck_gloss
--     - simplifier
--
-- Optional schema config (key = name space of the filter, default "typeduck_gloss"):
--   typeduck_gloss:
--     languages: [ eng ]   # any of eng hin urd nep ind, shown in this order
--     show_pos: true       # prefix the part of speech, e.g. "(n) Hong Kong"
--     separator: " / "     # between languages
--     max_length: 60       # characters shown per gloss, 0 = unlimited
--
-- Index format (lua/typeduck_gloss.txt in the user data directory), one line
-- per candidate text:   <text> \t <record> ( \30 <record> )*
-- with                  <record> = jyutping \31 pos \31 eng \31 hin \31 urd \31 nep \31 ind
-- and one record per pronunciation of the text.
--
-- Choosing the record: with `translator/spelling_hints` on, the comment of a
-- candidate is its Jyutping with tones ("hong4", "hoeng1 gong2") and selects
-- the record exactly. Without it the comment is empty and the typed code is
-- used instead, which may lack tones; the match then ignores tones and can
-- pick the wrong sense of a character such as 行 (hong2 bank / hong4 row).
--
-- Reverse lookups (`p Mandarin, `c Cangjie, ...): the candidates of these
-- segments carry no Jyutping, so the filter adds it from a second index,
-- lua/typeduck_readings.txt:   <text> \t <jyutping> ( \31 <jyutping> )*
-- with the most frequent pronunciation first, which also selects the record.

local M = {}

local INDEX = "lua/typeduck_gloss.txt"
local READINGS = "lua/typeduck_readings.txt"
local READING_SEPARATOR = ", "
local US, RS = "\31", "\30"
local FIELD = { jyutping = 1, pos = 2, eng = 3, hin = 4, urd = 5, nep = 6, ind = 7 }
local DEFAULT_LANGUAGES = { "eng" }
local DEFAULT_SEPARATOR = " / "
local DEFAULT_MAX_LENGTH = 60

-- Loaded indexes, shared by every session and schema of this Lua state.
local cache = nil
local readings_cache = nil

local function log_warn(msg)
  if log and log.warning then
    log.warning("[typeduck_gloss] " .. msg)
  end
end

function M.split(s, sep)
  local out, pos = {}, 1
  while true do
    local i = string.find(s, sep, pos, true)
    if not i then
      out[#out + 1] = string.sub(s, pos)
      return out
    end
    out[#out + 1] = string.sub(s, pos, i - 1)
    pos = i + #sep
  end
end

-- Read an index file into a table text -> packed records.
function M.load_index(path)
  local fh = io.open(path, "r")
  if not fh then
    return nil
  end
  local index = {}
  for line in fh:lines() do
    local tab = string.find(line, "\t", 1, true)
    if tab then
      index[string.sub(line, 1, tab - 1)] = string.sub(line, tab + 1)
    end
  end
  fh:close()
  return index
end

local function find_index(name, optional)
  local dirs = {}
  if rime_api then
    if rime_api.get_user_data_dir then
      dirs[#dirs + 1] = rime_api.get_user_data_dir()
    end
    if rime_api.get_shared_data_dir then
      dirs[#dirs + 1] = rime_api.get_shared_data_dir()
    end
  end
  for _, dir in ipairs(dirs) do
    local ok, index = pcall(M.load_index, dir .. "/" .. name)
    if ok and index then
      return index
    end
  end
  if not optional then
    log_warn("index not found: " .. name .. " (run install-jyutping.py)")
  end
  return {}
end

-- Forget the cached indexes (they are otherwise kept until Rime is redeployed).
function M.clear_cache()
  cache = nil
  readings_cache = nil
end

-- Drop syllable delimiters so "hoeng1 gong2" compares equal to "hoeng1gong2".
function M.normalize(s)
  return (string.gsub(s or "", "[ '’·%-\t]", ""))
end

local function detone(s)
  return (string.gsub(s, "%d", ""))
end

-- Pick the record of `packed` pronounced `key`: exact Jyutping first, then
-- ignoring tones, else the first record.
function M.pick_record(packed, key)
  local records = M.split(packed, RS)
  for i = 1, #records do
    records[i] = M.split(records[i], US)
  end
  if #records == 1 or key == "" then
    return records[1]
  end
  for _, fields in ipairs(records) do
    if M.normalize(fields[FIELD.jyutping]) == key then
      return fields
    end
  end
  local toneless = detone(key)
  for _, fields in ipairs(records) do
    if detone(M.normalize(fields[FIELD.jyutping])) == toneless then
      return fields
    end
  end
  return records[1]
end

-- Shorten `text` to at most `max` UTF-8 characters, marking the cut with "…".
function M.truncate(text, max)
  if max == nil or max <= 0 or #text <= max then
    return text
  end
  local count = 0
  for pos in text:gmatch("()[^\128-\191]") do
    count = count + 1
    if count > max then
      return (text:sub(1, pos - 1):gsub("[%s;,]+$", "")) .. "…"
    end
  end
  return text
end

-- Format the gloss of one record, or nil when it has none in `env.langs`.
function M.build_gloss(fields, env)
  local parts = {}
  for _, lang in ipairs(env.langs) do
    local value = FIELD[lang] and fields[FIELD[lang]]
    if value and value ~= "" then
      parts[#parts + 1] = value
    end
  end
  if #parts == 0 then
    return nil
  end
  local text = M.truncate(table.concat(parts, env.separator), env.max_length)
  local pos = fields[FIELD.pos]
  if env.show_pos and pos and pos ~= "" then
    text = "(" .. pos .. ") " .. text
  end
  return text
end

-- Return the comment to show for `cand`, or nil to leave it untouched.
function M.comment_for(cand, env)
  local packed = env.index[cand.text]
  local comment = cand.comment or ""
  local shown, key = comment, M.normalize(comment)
  if env.lookup then
    -- The comment and the typed code belong to the lookup, not to Cantonese.
    local readings = env.readings[cand.text]
    key = ""
    if readings then
      local list = M.split(readings, US)
      key = M.normalize(list[1])
      shown = table.concat(list, READING_SEPARATOR)
      if comment ~= "" then
        shown = comment .. "  " .. shown
      end
    end
  elseif key == "" then
    key = M.normalize(cand.preedit)
  end
  local gloss = packed and M.build_gloss(M.pick_record(packed, key), env)
  if not gloss then
    return shown ~= comment and shown or nil
  end
  if shown == "" then
    return gloss
  end
  return shown .. "  " .. gloss
end

function M.init(env)
  local ns = (env.name_space or "typeduck_gloss"):gsub("^%*", "")
  local config = env.engine.schema.config

  -- Each read is guarded: a librime-lua without one of these accessors must
  -- cost a default, not the whole filter (a failing init drops every candidate).
  env.langs = {}
  pcall(function()
    local list = config:get_list(ns .. "/languages")
    if list then
      for i = 0, list.size - 1 do
        local value = list:get_value_at(i)
        if value then
          env.langs[#env.langs + 1] = value:get_string()
        end
      end
    end
  end)
  if #env.langs == 0 then
    env.langs = DEFAULT_LANGUAGES
  end
  pcall(function() env.show_pos = config:get_bool(ns .. "/show_pos") end)
  pcall(function() env.separator = config:get_string(ns .. "/separator") end)
  pcall(function() env.max_length = config:get_int(ns .. "/max_length") end)
  env.separator = env.separator or DEFAULT_SEPARATOR
  env.max_length = env.max_length or DEFAULT_MAX_LENGTH

  if cache == nil then
    cache = find_index(INDEX)
  end
  env.index = cache
  if readings_cache == nil then
    readings_cache = find_index(READINGS, true)
  end
  env.readings = readings_cache
end

-- Called by librime-lua with the segment about to be filtered. The schema's
-- own translator tags its segments "abc"; every other tag is a reverse lookup.
function M.tags_match(segment, env)
  local ok, abc = pcall(function() return segment:has_tag("abc") end)
  env.lookup = ok and not abc
  return true
end

function M.func(input, env)
  for cand in input:iter() do
    local ok, comment = pcall(M.comment_for, cand, env)
    if ok and comment then
      -- Wrapped rather than assigned: setting cand.comment is a silent no-op
      -- in librime-lua for Shadow/Uniquified candidates.
      yield(ShadowCandidate(cand, cand.type, cand.text, comment))
    else
      yield(cand)
    end
  end
end

return M
