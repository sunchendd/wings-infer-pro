# G.PRE.05-CPP 所有\\#else、\\#elif、\\#endif和与之对应的\\#if、\\#ifdef、\\#ifndef预处理指令应出现在同一文件中

- **规则ID**：f206cdde-3869-4d6b-a4f8-e911b264ad45
- **更新时间**：2025-03-25 19:22:48

---

**【问题级别】**

严重

**【描述】**

当使用多个文件来构成这些预处理块时，难以直观发现代码块的关联，增加了阅读和维护的复杂度，从而更容易产生错误。





**【正确示例】**

```
// sample.h 开始  
#if defined(__VXWORKS__)    // 在相同文件中闭合该预处理块  
#include "vx_config.h"
#endif
// sample.h 结束  

```
**【错误示例】**

```
// sample.h 开始  
#if defined(__VXWORKS__)  // 未在相同文件中闭合该预处理块
#include "vx_config.h"

// 这里结束前，本应当有 #endif 与前面的 #if defined 形成闭合  
// sample.h 结束  

```
**【修复建议】**

预处理指令在同一个文件中闭合
