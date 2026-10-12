# G.MDL.02-TS 使用 import/export 代替 modules 和 namespace

- **规则ID**：49df31ff-742c-4184-b38b-8d36a9a5990a
- **更新时间**：2026-04-07 04:35:02

---

**【问题级别】**

提示

**【描述】**

标准化模块声明的定义，目前 module 和 namespace 语法已经被认为是过时的，且不利于 Tree shaking 优化，建议使用 ES6 模块。

**【正确示例】**

```
##### 场景1：import/export 代替 modules 和 namespace
- 修复示例：使用 import/export。

```typescript
// 例如在 module.ts 中声明如下：
export function foo() {}
export function bar() {}

// 在使用的时候，可使用 import .. as 语法定义命名空间：
import * as ns from 'module';
// 也可以单独引入所需的函数：
import { bar } from 'module';
```

```
**【错误示例】**

```
##### 场景1：import/export 代替 modules 和 namespace
- 错误示例：使用 modules 和 namespace。

```typescript
// TypeScript 1.6 对此语法已经不推荐使用
module foo {
    export function bar() {}
}

export default namespace ns {
  export function foo() {}
  export function bar() {}
}
// 在使用的时候，需要把整个命名空间导入：
import ns from 'module';
```

```
**【修复建议】**

使用 import/export 代替 modules 和 namespace。
