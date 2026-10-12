# G.INC.05 头文件应当自包含

- **规则ID**：7cadc7e5-1b9c-48fb-ae33-fbe41b5fa129
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

严重

**【描述】**

要求头文件自包含，即一个头文件被其它文件包含，不需要再引入其它额外依赖的头文件。

**【正确示例】**

```
##### 场景1：头文件没有自包含
- 修复示例：

```c
#ifndef DEBUG_FUNC_H
#define DEBUG_FUNC_H

#include  <stdio.h>  // 头文件要刚刚可以自包含，不能在头文件中多包含任何满足自包含之外的其它头文件。

#define  DEBUG_FUNC_START  printf("FUNC:[%s] start\
", __func__)  // 符合：头文件自包含

#endif
```


```
**【错误示例】**

```
##### 场景1：头文件没有自包含
- 错误示例：

```c
#ifndef DEBUG_FUNC_H
#define DEBUG_FUNC_H

#define  DEBUG_FUNC_START  printf("FUNC:[%s] start\
", __func__)  // 不符合：宏DEBUG_FUNC_START的实现需要依赖stdio.h，如果被该头文件被源文件包含，则源文件还需要引入额外的stdio.h。

#endif
```


```
**【修复建议】**

头文件包含所需头文件。

注意：该规则需要与 “[G.INC.04 禁止包含用不到的头文件]” 规则一起使用，头文件要刚刚可以自包含，不能在头文件中多包含任何满足自包含之外的其它头文件。
