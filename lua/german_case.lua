-- german_case.lua
-- librime-lua filter for the `deutsch` and `francais` schemas: while the context property
-- "german_capital" is "1" (set by german_keys.lua when the input starts with
-- an uppercase letter), the first letter of every candidate is capitalized:
-- "Ich" for ich, "Über" for über, "École" for école. Comments are kept, so this filter goes
-- after german_gloss, which looks the word up as the dictionary spells it.
--
-- Usage in a schema, after lua_filter@*german_gloss:
--   - lua_filter@*german_case

local M = {}

-- string.upper only knows ASCII; the letters of German and French words.
local UPPER = {
  ["ä"] = "Ä", ["ö"] = "Ö", ["ü"] = "Ü", ["à"] = "À", ["â"] = "Â", ["æ"] = "Æ",
  ["ç"] = "Ç", ["é"] = "É", ["è"] = "È", ["ê"] = "Ê", ["ë"] = "Ë", ["î"] = "Î",
  ["ï"] = "Ï", ["ô"] = "Ô", ["œ"] = "Œ", ["ù"] = "Ù", ["û"] = "Û", ["ÿ"] = "Ÿ",
}

-- `text` with its first letter in uppercase.
function M.capitalize(text)
  local first = text:match("^[%z\1-\127\194-\244][\128-\191]*")
  if not first then
    return text
  end
  local upper = UPPER[first] or first:upper()
  if upper == first then
    return text
  end
  return upper .. text:sub(#first + 1)
end

function M.func(input, env)
  if env.engine.context:get_property("german_capital") ~= "1" then
    for cand in input:iter() do
      yield(cand)
    end
    return
  end
  -- "essen" and "Essen" both become "Essen"; the first one (ranked higher) is kept.
  local seen = {}
  for cand in input:iter() do
    local text = M.capitalize(cand.text)
    if not seen[text] then
      seen[text] = true
      if text ~= cand.text then
        yield(ShadowCandidate(cand, cand.type, text, cand.comment))
      else
        yield(cand)
      end
    end
  end
end

return M
