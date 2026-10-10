-- Offline unit tests for lua/delimited_code.lua with mocked librime-lua objects.
-- Run from the repository root:  lua tests/test_delimited_code.lua
-- The Segmentation mock reproduces librime's Segmentation::AddSegment and
-- Forward (src/rime/segmentation.cc): within one round the longer segment
-- wins and equally long segments merge their tags.

package.path = "./lua/?.lua;" .. package.path

-- ---- mocks ---------------------------------------------------------------
function Segment(start_pos, end_pos)
  return { start = start_pos, _end = end_pos, tags = {} }
end

function Set(list)
  local set = {}
  for _, v in ipairs(list) do set[v] = true end
  return set
end

local function Segmentation(input, segments)
  local self = { input = input, segments = segments or {} }
  function self:get_current_start_position()
    local last = self.segments[#self.segments]
    return last and last.start or 0
  end
  function self:add_segment(seg)
    if seg.start ~= self:get_current_start_position() then return false end
    local last = self.segments[#self.segments]
    if not last then
      self.segments[1] = seg
    elseif last._end < seg._end then
      self.segments[#self.segments] = seg
    elseif last._end == seg._end then
      for tag in pairs(seg.tags) do last.tags[tag] = true end
    end
    return true
  end
  function self:forward()
    local last = self.segments[#self.segments]
    self.segments[#self.segments + 1] = Segment(last._end, last._end)
  end
  return self
end

local function mock_env(values, name_space)
  return {
    name_space = name_space or "*delimited_code",
    engine = { schema = { config = {
      get_string = function(_, key) return values and values[key] end,
    } } },
  }
end

-- ---- tests ---------------------------------------------------------------
local dc = require("delimited_code")
local failures, total = 0, 0
local function check(name, cond)
  total = total + 1
  if not cond then
    failures = failures + 1
    print("FAIL: " .. name)
  end
end

-- 1. piece_length
local AZ, DELIM = "zyxwvutsrqponmlkjihgfedcba", " ;"
check("code + delimiter", dc.piece_length("vmpi;dl", AZ, DELIM) == 5)
check("no delimiter", dc.piece_length("vmpidl", AZ, DELIM) == nil)
check("trailing delimiter", dc.piece_length("dl;", AZ, DELIM) == 3)
check("repeated delimiters consumed", dc.piece_length("vmpi;;dl", AZ, DELIM) == 6)
check("leading delimiter", dc.piece_length(";dl", AZ, DELIM) == nil)
check("non-alphabet first", dc.piece_length("`yue;", AZ, DELIM) == nil)
check("non-alphabet before delimiter", dc.piece_length("ab1;", AZ, DELIM) == nil)
check("empty", dc.piece_length("", AZ, DELIM) == nil)
check("x code", dc.piece_length("xykq;dl", AZ, DELIM) == 5)
check("magic characters are literal", dc.piece_length("a.b%", "ab.", "%") == 4)

-- 2. init reads the speller settings, with defaults
local env = mock_env({ ["speller/alphabet"] = "abc", ["speller/delimiter"] = ";" })
dc.init(env)
check("alphabet from config", env.code_alphabet == "abc")
check("delimiter from config", env.code_delimiters == ";")
check("default tag", env.code_tag == "abc")
local env2 = mock_env({ ["seg/tag"] = "cangjie" }, "seg")
dc.init(env2)
check("default alphabet", env2.code_alphabet == AZ)
check("default delimiter", env2.code_delimiters == " '")
check("tag from custom name space", env2.code_tag == "cangjie")

-- 3. segmentor: first round takes "vmpi;" and stops the round
local cj = mock_env({ ["speller/alphabet"] = AZ, ["speller/delimiter"] = DELIM })
dc.init(cj)
local s = Segmentation("vmpi;dl")
check("delimited round stops", dc.func(s, cj) == false)
check("first segment", #s.segments == 1 and s.segments[1].start == 0 and s.segments[1]._end == 5)
check("segment tagged abc", s.segments[1].tags.abc == true)
s:forward()
check("last piece left to abc_segmentor", dc.func(s, cj) == true)
check("no segment added for last piece", s.segments[2]._end == 5)

-- 4. three pieces
local s3 = Segmentation("vmpi;dl;jbmm")
dc.func(s3, cj); s3:forward()
check("second round stops", dc.func(s3, cj) == false)
check("second segment", s3.segments[2].start == 5 and s3.segments[2]._end == 8)

-- 5. plain input is untouched
local s4 = Segmentation("vmpidl")
check("plain input passes", dc.func(s4, cj) == true and #s4.segments == 0)

-- 6. librime keeps the previous keystroke's segment; ours replaces a shorter
--    one and never shrinks a longer one found by the matcher
local stale = Segment(0, 4)
stale.tags = Set({ "abc" })
local s5 = Segmentation("vmpi;", { stale })
check("stale shorter segment: round stops", dc.func(s5, cj) == false)
check("stale shorter segment replaced", #s5.segments == 1 and s5.segments[1]._end == 5)
local matched = Segment(0, 8)
matched.tags = Set({ "reverse_lookup" })
local s6 = Segmentation("vmpi;dl'", { matched })
dc.func(s6, cj)
check("longer matcher segment kept",
  s6.segments[1]._end == 8 and s6.segments[1].tags.reverse_lookup and not s6.segments[1].tags.abc)

print(string.format("%d/%d checks passed", total - failures, total))
os.exit(failures == 0 and 0 or 1)
