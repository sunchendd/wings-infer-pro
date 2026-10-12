# G.FMT.02 一个源文件按顺序包含版权、package、import、顶层类，且用空行分隔

- **规则ID**：db6a3b64-ed35-43b2-b709-2a7be8b6218c
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

一个源文件中应按顺序包含以下信息：



1. 许可证或版权信息；

2. package语句，且语句内不换行；

3. import语句，且语句内不换行，不能用通配符*；

4. 顶级类（只有一个），所在.java源文件与它同名。



以上每个部分之间用一个空行隔开。

**【正确示例】**

```
##### 场景1：版权、package、import、顶层类按推荐顺序排列
- 修复示例：版权、package、import、顶层类之间使用一个空行分隔

```java
/**
 * Copyright (c) Huawei Technologies Co., Ltd. 2012-2019. All rights reserved.
 */

package com.puppycrawl.tools.checkstyle;

import java.util.List;

/**
 * JavaComponentOrder介绍
 *
 * @since 2023-08-29
 */
public class JavaComponentOrder {
}
```


```
**【错误示例】**

```
##### 场景1：版权、package、import、顶层类按推荐顺序排列
- 错误示例：版权、package的顺序错误，分隔使用多个空行

```java
package com.puppycrawl.tools.checkstyle;

/**
 * Copyright (c) Huawei Technologies Co., Ltd. 2012-2019. All rights reserved.
 */


import java.util.List;

/**
 * JavaComponentOrder介绍
 *
 * @since 2023-08-29
 */
public class JavaComponentOrder {
}

```


```
**【修复建议】**

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
