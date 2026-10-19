-- Offline unit tests for lua/german_keys.lua and lua/german_case.lua with
-- mocked librime-lua objects. Run from the repository root:
--   lua tests/test_german_keys.lua
-- The Context mock calls the commit notifier the way librime's
-- Context::Commit does: the engine's handler (connected first) commits the
-- candidate, then the other handlers run, then the input is cleared.

package.path = "./lua/?.lua;" .. package.path

-- ---- mocks ---------------------------------------------------------------
local function Notifier()
  local self = { slots = {} }
  function self:connect(fn)
    local slot = { fn = fn }
    table.insert(self.slots, slot)
    return { disconnect = function() slot.fn = nil end }
  end
  function self:emit(ctx)
    for _, slot in ipairs(self.slots) do
      if slot.fn then slot.fn(ctx) end
    end
  end
  return self
end

local function Engine(values)
  local committed = {}
  local ctx = { input = "", props = {}, options = {}, selected = nil,
                commit_notifier = Notifier(), update_notifier = Notifier() }
  function ctx:is_composing() return self.input ~= "" end
  function ctx:get_property(k) return self.props[k] or "" end
  function ctx:set_property(k, v) self.props[k] = v end
  function ctx:get_option(k) return self.options[k] or false end
  function ctx:push_input(s)
    self.input = self.input .. s
    self.update_notifier:emit(self)
  end
  function ctx:clear()
    self.input = ""
    self.update_notifier:emit(self)
  end
  local engine = {
    context = ctx,
    schema = { config = {
      get_bool = function(_, key) return values and values[key] end,
    } },
  }
  function engine:commit_text(text) committed[#committed + 1] = text end
  -- What selector does for Space: commit the selected candidate.
  function ctx:commit()
    engine:commit_text(self.selected or self.input)
    self.commit_notifier:emit(self)
    self:clear()
  end
  ctx.commit_notifier:connect(function() end) -- the engine's own handler
  return engine, committed
end

local function KeyEvent(repr, keycode, mods)
  mods = mods or {}
  return {
    keycode = keycode,
    repr = function() return repr end,
    release = function() return mods.release or false end,
    ctrl = function() return mods.ctrl or false end,
    alt = function() return mods.alt or false end,
    super = function() return false end,
  }
end

local SPACE = KeyEvent("space", 0x20)
local function letter(ch) return KeyEvent(ch, ch:byte()) end

local function Candidate(text, comment)
  return { text = text, comment = comment or "", type = "table" }
end

function ShadowCandidate(cand, typ, text, comment)
  return { text = text, comment = comment, type = typ, shadowed = cand }
end

local yielded
function yield(cand) yielded[#yielded + 1] = cand end

local function Translation(cands)
  return { iter = function()
    local i = 0
    return function() i = i + 1; return cands[i] end
  end }
end

local function filter(module, env, cands)
  yielded = {}
  module.func(Translation(cands), env)
  return yielded
end

-- ---- tests ---------------------------------------------------------------
local keys = require("german_keys")
local case = require("german_case")
local failures, total = 0, 0
local function check(name, cond)
  total = total + 1
  if not cond then
    failures = failures + 1
    print("FAIL: " .. name)
  end
end

-- 1. Space after a word committed with Space
local engine, committed = Engine()
local env = { engine = engine, name_space = "*german_keys" }
keys.init(env)
for ch in ("haus"):gmatch(".") do engine.context:push_input(ch) end
engine.context.selected = "Haus"
check("space is left to the selector", keys.func(SPACE, env) == 2)
engine.context:commit()
check("word then space", table.concat(committed, "|") == "Haus| ")

-- 2. Space while not composing adds nothing
committed[#committed] = nil
committed[#committed] = nil
check("idle space is left alone", keys.func(SPACE, env) == 2)
check("idle space commits nothing", #committed == 0)

-- 3. Other commits (digit, punctuation) add no space
engine.context:push_input("haus")
keys.func(letter("1"), env)
engine.context:commit()
check("digit commit: no space", #committed == 1 and committed[1] == "Haus")

-- 4. Space then a key that did not commit: the flag does not leak
committed[1] = nil
engine.context:push_input("haus")
keys.func(SPACE, env)
keys.func(letter(","), env)
engine.context:commit()
check("flag reset by the next key", #committed == 1)

-- 5. auto_space: false
local engine2, committed2 = Engine({ ["german_keys/auto_space"] = false })
local env2 = { engine = engine2, name_space = "*german_keys" }
keys.init(env2)
engine2.context:push_input("haus")
keys.func(SPACE, env2)
engine2.context:commit()
check("auto_space off", #committed2 == 1)

-- 6. Capitals: Shift+I first is entered as "i" and sets the property
committed[1] = nil
check("uppercase accepted", keys.func(KeyEvent("Shift+I", 0x49), env) == 1)
check("entered lowercase", engine.context.input == "i")
check("capital property set", engine.context:get_property("german_capital") == "1")
keys.func(KeyEvent("Shift+C", 0x43), env)
check("later capital also lowercase", engine.context.input == "ic")
engine.context:clear()
check("property cleared with the input", engine.context:get_property("german_capital") == "")
engine.context:push_input("i")
check("lowercase start: no property", engine.context:get_property("german_capital") == "")
keys.func(KeyEvent("Shift+C", 0x43), env)
check("capital later in the word: no property", engine.context:get_property("german_capital") == "")
engine.context:clear()

-- 7. Modified, released and ASCII-mode keys are not touched
check("ctrl ignored", keys.func(KeyEvent("Control+A", 0x41, { ctrl = true }), env) == 2)
check("release ignored", keys.func(KeyEvent("Release+A", 0x41, { release = true }), env) == 2)
engine.context.options.ascii_mode = true
check("ascii mode ignored", keys.func(KeyEvent("Shift+A", 0x41), env) == 2)
check("nothing entered", engine.context.input == "")
engine.context.options.ascii_mode = false

-- 8. fini disconnects
keys.fini(env)
engine.context:push_input("haus")
keys.func(SPACE, env)
engine.context:commit()
check("no space after fini", #committed == 1)

-- 9. german_case.capitalize
check("ascii", case.capitalize("ich") == "Ich")
check("umlaut", case.capitalize("über") == "Über")
check("already capital", case.capitalize("Haus") == "Haus")
check("empty", case.capitalize("") == "")
check("rest untouched", case.capitalize("äöü") == "Äöü")

-- 10. german_case filter
local e3 = Engine()
local cenv = { engine = e3 }
local plain = filter(case, cenv, { Candidate("essen", " 吃"), Candidate("Essen", " 食物") })
check("no property: unchanged", #plain == 2 and plain[1].text == "essen" and plain[2].text == "Essen")
e3.context:set_property("german_capital", "1")
local out = filter(case, cenv, { Candidate("essen", " 吃"), Candidate("Essen", " 食物"),
                                 Candidate("über", " 在上面") })
check("capitalized, duplicate dropped", #out == 2)
check("first keeps its comment", out[1].text == "Essen" and out[1].comment == " 吃" and out[1].shadowed)
check("umlaut capitalized", out[2].text == "Über" and out[2].comment == " 在上面")

print(string.format("%d/%d checks passed", total - failures, total))
os.exit(failures == 0 and 0 or 1)
