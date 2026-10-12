# G.MDL.01-TS 统一使用 import type 导入类型

- **规则ID**：5a2c06fb-13e2-47c1-92b1-ea715508a809
- **更新时间**：2025-06-05 04:35:03

---

**【问题级别】**

提示

**【描述】**

在导入类型时，加上type的标志，有利于区分仅导入“类型”还是导入实体，使用 import type ，只会引入类型本身，不会执行模块全局代码，如果需要初始化模块，需要显式使用import '...' 。当仅导入类型时，在编译成 JavaScript 时会被消除，从而避免引入不必要的文件。

**【正确示例】**

```
import type { Foo } from 'Foo';
import type Bar from 'Bar';
type T = Foo;
const bar: Bar = 1;

```
**【错误示例】**

```
import { Foo } from 'Foo';
import Bar from 'Bar';
type T = Foo;
const bar: Bar = 1;

```
**【修复建议】**

统一使用 import type 导入类型
