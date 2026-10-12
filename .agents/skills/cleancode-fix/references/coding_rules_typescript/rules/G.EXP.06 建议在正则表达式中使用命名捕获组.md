# G.EXP.06 建议在正则表达式中使用命名捕获组

- **规则ID**：91ef82fe-9a20-42f3-876e-172da45528ae
- **更新时间**：2026-04-07 04:35:01

---

**【问题级别】**

提示

**【描述】**

随着 ECMAScript 2018 的发布，命名捕获组可以用于正则表达式中，这可以提高正则表达式的可读性。

**【正确示例】**

```
##### 场景1：正则表达式
- 修复示例：使用命名捕获组。

```javascript
const foo = /(?<id>ba[rz])/;
const bar = new RegExp('(?<id>ba[rz])');
const baz = RegExp('(?<id>ba[rz])');

foo.exec('bar').groups.id;

```

```
**【错误示例】**

```
##### 场景1：正则表达式
- 错误示例：不使用命名捕获组。

```javascript
const foo = /(ba[rz])/;
const bar = new RegExp('(ba[rz])');
const baz = RegExp('(ba[rz])');

foo.exec('bar')[1];
```

```
**【修复建议】**

建议在正则表达式中使用命名捕获组。
