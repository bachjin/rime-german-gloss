-- german_gloss.lua
-- librime-lua filter: append an offline German gloss to candidate comments.
--
-- Usage in a schema (or <schema>.custom.yaml patch):
--   engine/filters/@next: lua_filter@*german_gloss
--
-- Optional schema config (key = name space of the filter, default "german_gloss"):
--   german_gloss:
--     dictionary: german_gloss/zh_de.tsv   # relative to user/shared data dir, or absolute
--     opencc_config: t2s.json              # "none" disables script normalization
--
-- Script normalization: dictionary keys and candidate texts are both mapped
-- to Simplified Chinese with OpenCC (default t2s.json, the same file librime's
-- simplifier uses), so one dictionary serves Traditional and Simplified output.
-- Exact matches take precedence over normalized ones.
--
-- Dictionary format: UTF-8 TSV, one entry per line: <Chinese>\t<German>.
-- Empty lines and lines starting with '#' are ignored. Repeated keys are
-- joined with "; " in file order (exact duplicates are dropped).

local M = {}

local DEFAULT_DICT = "german_gloss/zh_de.tsv"
local DEFAULT_OPENCC = "t2s.json"

local function log_warn(msg)
  if log and log.warning then
    log.warning("[german_gloss] " .. msg)
  end
end

local function trim(s)
  return (s:gsub("^%s+", ""):gsub("%s+$", ""))
end

-- Parse TSV content from an open file handle into a table text -> gloss.
function M.parse(fh)
  local dict = {}
  local first = true
  for line in fh:lines() do
    if first then
      line = line:gsub("^\239\187\191", "") -- strip UTF-8 BOM
      first = false
    end
    line = line:gsub("\r$", "")             -- tolerate CRLF files
    if line ~= "" and line:sub(1, 1) ~= "#" then
      local key, gloss = line:match("^([^\t]+)\t(.+)$")
      if key then
        key, gloss = trim(key), trim(gloss)
        if key ~= "" and gloss ~= "" then
          local old = dict[key]
          if old == nil then
            dict[key] = gloss
          elseif old ~= gloss
              and ("; " .. old .. "; "):find("; " .. gloss .. "; ", 1, true) == nil then
            dict[key] = old .. "; " .. gloss
          end
        end
      end
    end
  end
  return dict
end

local function is_absolute(path)
  return path:sub(1, 1) == "/" or path:match("^%a:[/\\]") ~= nil
      or path:sub(1, 2) == "\\\\"
end

local function resolve_path(rel)
  if is_absolute(rel) then
    return { rel }
  end
  local paths = {}
  if rime_api then
    if rime_api.get_user_data_dir then
      paths[#paths + 1] = rime_api.get_user_data_dir() .. "/" .. rel
    end
    if rime_api.get_shared_data_dir then
      paths[#paths + 1] = rime_api.get_shared_data_dir() .. "/" .. rel
    end
  end
  return paths
end

function M.load(rel)
  for _, path in ipairs(resolve_path(rel)) do
    local fh = io.open(path, "r")
    if fh then
      local dict = M.parse(fh)
      fh:close()
      return dict, path
    end
  end
  log_warn("dictionary not found: " .. rel)
  return {}, nil
end

-- Return the comment to show for a candidate with comment `old` and gloss `gloss`.
function M.merge_comment(old, gloss)
  if old == nil or old == "" then
    return " " .. gloss
  end
  return old .. " " .. gloss
end

-- Return a candidate carrying the merged comment. Setting cand.comment is a
-- silent no-op in librime-lua for Shadow/Uniquified candidates (e.g. produced
-- by simplifier or uniquifier), so fall back to wrapping in a ShadowCandidate.
function M.annotate(cand, gloss)
  local comment = M.merge_comment(cand.comment, gloss)
  cand.comment = comment
  if cand.comment == comment then
    return cand
  end
  return ShadowCandidate(cand, cand.type, cand.text, comment)
end

-- Return an OpenCC converter for `name`, or nil if unavailable
-- (librime-lua without Opencc support, or config file not found).
function M.make_converter(name)
  if name == nil or name == "" or name == "none" or Opencc == nil then
    return nil
  end
  local ok, conv = pcall(Opencc, name)
  if ok and conv then
    return conv
  end
  log_warn("OpenCC config unavailable, script normalization disabled: " .. name)
  return nil
end

-- Add normalized aliases for keys whose normalized form is not yet present.
function M.add_aliases(dict, conv)
  local aliases = {}
  for key, gloss in pairs(dict) do
    local norm = conv:convert(key)
    if norm ~= key and dict[norm] == nil and aliases[norm] == nil then
      aliases[norm] = gloss
    end
  end
  for key, gloss in pairs(aliases) do
    dict[key] = gloss
  end
end

-- Exact match first, then match on the normalized text.
function M.lookup(dict, conv, text)
  local gloss = dict[text]
  if gloss == nil and conv ~= nil then
    local norm = conv:convert(text)
    if norm ~= text then
      gloss = dict[norm]
    end
  end
  return gloss
end

function M.init(env)
  local ns = (env.name_space or ""):gsub("^%*", "")
  if ns == "" then ns = "german_gloss" end
  local rel = DEFAULT_DICT
  local opencc_config = DEFAULT_OPENCC
  local config = env.engine and env.engine.schema and env.engine.schema.config
  if config then
    local v = config:get_string(ns .. "/dictionary")
    if v and v ~= "" then rel = v end
    local o = config:get_string(ns .. "/opencc_config")
    if o then opencc_config = o end
  end
  env.gloss_dict = M.load(rel)
  env.gloss_conv = M.make_converter(opencc_config)
  if env.gloss_conv then
    M.add_aliases(env.gloss_dict, env.gloss_conv)
  end
end

function M.func(input, env)
  local dict = env.gloss_dict or {}
  local conv = env.gloss_conv
  for cand in input:iter() do
    local gloss = M.lookup(dict, conv, cand.text)
    if gloss then
      yield(M.annotate(cand, gloss))
    else
      yield(cand)
    end
  end
end

function M.fini(env)
  env.gloss_dict = nil
  env.gloss_conv = nil
end

return M
