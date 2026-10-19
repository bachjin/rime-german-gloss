-- german_keys.lua
-- librime-lua processor for the `deutsch` schema, whose codes are lowercase
-- ASCII (Straße -> strasse). It does two things:
--
-- 1. Space after a word: when Space commits a candidate, a space is committed
--    after it, so words typed one after another come out separated ("Haus"
--    Space "ist" Space gives "Haus ist "). Other ways of committing (digits,
--    Enter, punctuation) add nothing, so "haus," still gives "Haus,".
-- 2. Capitals: an uppercase letter typed first (Shift+I) is entered as its
--    lowercase code, and the context property "german_capital" is set to "1"
--    until the input is cleared; german_case.lua then capitalizes the
--    candidates ("Ich", "Für"). Without this the letter would bypass Rime.
--
-- Usage in a schema, before speller:
--   - lua_processor@*german_keys
--
-- Optional schema config (key = name space of the processor, default "german_keys"):
--   german_keys:
--     auto_space: true

local M = {}

local kAccepted = 1
local kNoop = 2
local PROPERTY = "german_capital"

function M.init(env)
  local ns = (env.name_space or ""):gsub("^%*", "")
  if ns == "" then
    ns = "german_keys"
  end
  local config = env.engine.schema.config
  env.keys_auto_space = config:get_bool(ns .. "/auto_space") ~= false
  env.keys_space_pending = false
  local context = env.engine.context
  -- The engine's own commit handler was connected first, so the candidate is
  -- already committed when this one runs.
  env.keys_commit = context.commit_notifier:connect(function(ctx)
    if env.keys_space_pending then
      env.keys_space_pending = false
      env.engine:commit_text(" ")
    end
  end)
  env.keys_update = context.update_notifier:connect(function(ctx)
    if not ctx:is_composing() and ctx:get_property(PROPERTY) ~= "" then
      ctx:set_property(PROPERTY, "")
    end
  end)
end

function M.func(key, env)
  if key:release() or key:ctrl() or key:alt() or key:super() then
    return kNoop
  end
  local context = env.engine.context
  if context:get_option("ascii_mode") then
    return kNoop
  end
  local code = key.keycode
  if code >= 0x41 and code <= 0x5a then -- A-Z
    if not context:is_composing() then
      context:set_property(PROPERTY, "1")
    end
    context:push_input(string.char(code + 32))
    return kAccepted
  end
  env.keys_space_pending = env.keys_auto_space and key:repr() == "space"
      and context:is_composing()
  -- Leave the key to selector / editor, which do the actual commit.
  return kNoop
end

function M.fini(env)
  for _, name in ipairs({ "keys_commit", "keys_update" }) do
    if env[name] then
      env[name]:disconnect()
      env[name] = nil
    end
  end
end

return M
