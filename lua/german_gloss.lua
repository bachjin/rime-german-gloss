-- german_gloss.lua
-- librime-lua filter: append an offline German gloss to candidate comments.
--
-- Usage in a schema (or <schema>.custom.yaml patch):
--   engine/filters/@next: lua_filter@*german_gloss
--
-- Optional schema config (key = name space of the filter, default "german_gloss"):
--   german_gloss:
--     dictionary: german_gloss/zh_de.tsv   # relative to user/shared data dir, or absolute
--
-- Dictionary format: UTF-8 TSV, one entry per line: <Chinese>\t<German>.
-- Empty lines and lines starting with '#' are ignored. Repeated keys are
-- joined with "; " in file order (exact duplicates are dropped).

local M = {}

local DEFAULT_DICT = "german_gloss/zh_de.tsv"

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

function M.init(env)
  local ns = (env.name_space or ""):gsub("^%*", "")
  if ns == "" then ns = "german_gloss" end
  local rel = DEFAULT_DICT
  local config = env.engine and env.engine.schema and env.engine.schema.config
  if config then
    local v = config:get_string(ns .. "/dictionary")
    if v and v ~= "" then rel = v end
  end
  env.gloss_dict = M.load(rel)
end

function M.func(input, env)
  local dict = env.gloss_dict or {}
  for cand in input:iter() do
    local gloss = dict[cand.text]
    if gloss then
      yield(M.annotate(cand, gloss))
    else
      yield(cand)
    end
  end
end

function M.fini(env)
  env.gloss_dict = nil
end

return M
