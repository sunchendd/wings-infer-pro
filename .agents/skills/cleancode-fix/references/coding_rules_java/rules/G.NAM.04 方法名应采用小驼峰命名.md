# G.NAM.04 方法名应采用小驼峰命名

- **规则ID**：23b1155a-24e6-4c33-90df-747162b03320
- **更新时间**：2026-04-07 04:00:00

---

**【问题级别】**

提示

**【描述】**

方法名通常是动词或动词短语，采用**小驼峰命名**。

**【正确示例】**

```
##### 场景1
- 修复示例
  ```java
  public boolean isFinished() // 【GOOD】Finished()--> isFinished()

  public void draw() // 【GOOD】DRAW()-->draw()

  public void addKeyListener(Listener) // 【GOOD】KeyListener(Listener)-->addKeyListener(Listener)
  ```


```
**【错误示例】**

```
##### 场景1
- 错误示例
  ```java
  public boolean Finished() // 【不符合】大驼峰命名。

  public void DRAW() // 【不符合】

  public void KeyListener(Listener) // 【不符合】

  ```


```
**【修复建议】**

方法名采用小驼峰命名。
