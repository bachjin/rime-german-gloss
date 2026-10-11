-- delimited_code.lua
-- librime-lua segmentor for table schemas (Cangjie, Wubi, ...): a delimiter
-- typed after a code ends that code. "vmpi;dl" becomes two segments, "vmpi;"
-- and "dl", and the table translator looks each one up as a whole code, so
-- its sentence maker can no longer re-split the input ("vm" + "pi" + "dl").
--
-- Usage in a schema (or <schema>.custom.yaml patch), before abc_segmentor:
--   engine/segmentors/@before 2: lua_segmentor@*delimited_code
--
-- Alphabet and delimiters are read from speller/alphabet and
-- speller/delimiter. Optional schema config (key = name space of the
-- segmentor, default "delimited_code"):
--   delimited_code:
--     tag: abc   # tag given to each segment; must be one the translator accepts

local M = {}

local DEFAULT_ALPHABET = "zyxwvutsrqponmlkjihgfedcba"
local DEFAULT_DELIMITERS = " '"
local DEFAULT_TAG = "abc"

-- Length of the leading "<code><delimiters>" piece of `rest`, or nil when
-- `rest` does not start with a code that is followed by a delimiter.
function M.piece_length(rest, alphabet, delimiters)
  local n = #rest
  local i = 1
  while i <= n and alphabet:find(rest:sub(i, i), 1, true) do
    i = i + 1
  end
  if i == 1 then
    return nil
  end
  local j = i
  while j <= n and delimiters:find(rest:sub(j, j), 1, true) do
    j = j + 1
  end
  if j == i then
    return nil
  end
  return j - 1
end

local function config_string(config, key, default)
  local value = config:get_string(key)
  if value == nil or value == "" then
    return default
  end
  return value
end

function M.init(env)
  local config = env.engine.schema.config
  local ns = (env.name_space or ""):gsub("^%*", "")
  if ns == "" then
    ns = "delimited_code"
  end
  env.code_alphabet = config_string(config, "speller/alphabet", DEFAULT_ALPHABET)
  env.code_delimiters = config_string(config, "speller/delimiter", DEFAULT_DELIMITERS)
  env.code_tag = config_string(config, ns .. "/tag", DEFAULT_TAG)
end

function M.func(segmentation, env)
  local start = segmentation:get_current_start_position()
  local len = M.piece_length(segmentation.input:sub(start + 1),
                             env.code_alphabet, env.code_delimiters)
  if not len then
    return true
  end
  local seg = Segment(start, start + len)
  seg.tags = Set({ env.code_tag })
  -- A longer segment already found in this round (matcher) is kept by add_segment.
  segmentation:add_segment(seg)
  -- Stop this round, or abc_segmentor would extend the segment to the whole input.
  return false
end

return M
