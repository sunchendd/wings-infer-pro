# G.CTL.01 不要在控制性条件表达式中执行赋值操作或执行复杂的条件判断

- **规则ID**：0a08b765-a13d-4389-9af6-cee6ec4cad01
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

控制性条件表达式常用于if、while、for、?:等条件判断中。



在控制性条件表达式中执行赋值或执行复杂的条件判断，常常导致意料之外的行为，且代码的可读性非常差。



复杂的条件判断是指在一个条件表达式中boolean运算符数量超过3。对于复杂的条件判断建议封装到一个独立的方法中，通过具有描述性的方法名让代码阅读者更容易理解复杂判断的目的，另外也方便对独立方法中的复杂条件判断逐步进行优化，最终使代码主流程和判断逻辑更加清晰可读。

**【正确示例】**

```
##### 场景1：boolean型变量不要直接与true/false比较
- 修复示例：

  ```java
  if (isFoo) 
  ```
##### 场景2：不要在条件表达式中进行赋值操作
- 修复示例：

  ```java
  public void fun(boolean isBar) {
      boolean isFoo = isBar;   // 在上面赋值，if条件判断中直接使用
      if (isFoo) {
          ...
      }
  }
  ```
##### 场景3：避免使用复杂的条件判断
- 修复示例1：将判断的条件以业务逻辑判断，单独抽取出method。

  ```java
  protected void addSpecialDataCol(String ciName, String ciLink, List<Object> rowList, String scriptPackageName) {
      String csvDir = "";
      if (this.scriptPackageName.toUpperCase(Locale.ROOT).contains("SWAP_")) {
          csvDir = this.objCIRM.getGlobalInfoMap().get("csvDir");
      }
      rowList.add(ciLink);
      
      // 将上述代码 if 逻辑判断部分，按照业务逻辑进行拆分。
      if (isLte() || isNr()) {
          String ciModeMark = getCIModeMark(ciName);
          rowList.add(ciModeMark);
      }
      rowList.add(csvDir);
      addNeCols(ciName, rowList);
  }
  private boolean isNr() {
      return "NR_NetworkInspection".equalsIgnoreCase(this.scriptPackageName)
      || "His_NR_NetworkInspection".equalsIgnoreCase(this.scriptPackageName);
  }
  private boolean isLte() {
      return StringUtil.containsIgnoreCase(this.scriptPackageName, "ONE_LTE")
          || "LTE_NetworkInspection".equalsIgnoreCase(this.scriptPackageName)
          || "His_LTE_NetworkInspection".equalsIgnoreCase(this.scriptPackageName);
  }
  ```
- 修复示例2：将复杂条件判断抽取为有含义的方法
  ```java
  private boolean isInvalidExecParams(String params) {
      return params.contains("!") || params.contains(";") || params.contains("&") || params.contains("$")
          || params.contains(">") || params.contains("<") || params.contains("`") || params.contains("\\")
          || params.contains(System.lineSeparator()) || params.contains("/") || params.contains("|");
  }
  ```
- 修复示例3：将复杂条件判断调整为正则检查
  ```java
  private static final Pattern CHAR_CHECK = Pattern.compile("[!;&$><`\\\\r
/|]");
  
  private boolean isInvalidExecParams(String params) {
      return CHAR_CHECK.matcher(params).find();
  }  
  ```
- 修复示例4：将复杂的条件判断调整为集合包含检查
  ```java
  List<String> conditionList = new ArrayList<>();
  conditionList.add(TY_STRINGVALUETY_STRINGVALUE.toUpperCase(Locale.ROOT));
  conditionList.add(TY_BOOLEANVALUE.toUpperCase(Locale.ROOT));
  ...
  conditionList.add(TY_TIMESTAMPVALUE.toUpperCase(Locale.ROOT));
  
  // 条件判断可直接简化为判断集合中是否包含该条件元素
  if(conditionList.contains(table.toUpperCase(Locale.ROOT))) {
      // 其他代码...
  }  
  ```


```
**【错误示例】**

```
##### 场景1：boolean型变量不要直接与true/false比较
- 错误示例：

  ```java
  if (isFoo = false)  // 在控制性判断中赋值不易理解
  if (isFoo == false) // 冗余不简洁，容易出错
  if (false == isFoo) // 冗余不简洁，容易出错
  ```
##### 场景2：不要在条件表达式中进行赋值操作
- 错误示例：

  ```java
  public void fun(boolean isBar) {
      boolean isFoo;
      if (isFoo = isBar) {
          ...
      }
  }
  ```
##### 场景3：避免使用复杂的条件判断
- 错误示例1：

  ```java
  protected void addSpecialDataCol(String ciName, String ciLink, List<Object> rowList, String scriptPackageName) {
      String csvDir = "";
      if (this.scriptPackageName.toUpperCase().contains("SWAP_")) {
          csvDir = this.objCIRM.getGlobalInfoMap().get("csvDir");
      }
      rowList.add(ciLink);
      
      // 此处的 if 逻辑判断较为复杂。
      if (StringUtil.containsIgnoreCase(this.scriptPackageName, "ONE_LTE")
          || "LTE_NetworkInspection".equalsIgnoreCase(this.scriptPackageName)
          || "His_LTE_NetworkInspection".equalsIgnoreCase(this.scriptPackageName)
          || "NR_NetworkInspection".equalsIgnoreCase(this.scriptPackageName)
          || "His_NR_NetworkInspection".equalsIgnoreCase(this.scriptPackageName)) {
          String ciModeMark = getCIModeMark(ciName);
          rowList.add(ciModeMark);
      }
      rowList.add(csvDir);
      addNeCols(ciName, rowList);
  }
  ```


```
**【修复建议】**

1、对于boolean型变量，在if判断中避免重复与true/false进行比较；

2、在条件判断中不要进行赋值操作；

3、对于复杂条件判断，建议结合业务场景进行合理的优化，比如：结合业务逻辑进行合理拆分、封装独立方法等，具体可参考代码示例中的场景3。
