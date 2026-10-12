# G.FMT.05-03 水平空格要突出关键字和重要信息

- **规则ID**：b7621d75-a1d4-40aa-a0f8-c6a497a70b32
- **更新时间**：2026-04-07 04:45:01

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：注释符与注释内容间要有空格

**【正确示例】**

```
```
local t = { -10, 0, 10 )
local sum = t[1] + t[2] + t[3]
local add = function(a, b) return a + b end
```

```
**【错误示例】**

```
```
local t={-10,0,10)
local sum=t[1]+t[2]+t[3]
local add=function(a,b) return a+b end
```

```
**【修复建议】**

逗号(,)，分号(;) 紧跟前方内容，后跟空格
