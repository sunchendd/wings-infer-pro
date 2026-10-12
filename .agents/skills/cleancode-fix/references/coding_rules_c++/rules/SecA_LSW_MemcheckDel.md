# SecA_LSW_MemcheckDel

- **规则ID**：05903870-6ada-4a1f-beb4-9e839590d3a0
- **更新时间**：2025-03-25 19:23:55

---

**【问题级别】**

一般

**【描述】**

节点从链表中删除后，需要自己释放节点的内存。

**【正确示例】**

```


```
**【错误示例】**

```
【Instruction】&nbsp;&nbsp;节点从链表中删除后，需要自己释放节点的内存。由于函数参数原因，一级指针导致函数模型
*   无法生效（模拟申请内存行为通过参数带回需要VOID **）
*   自定义规则检查从链表Delete节点后是否释放，如果未释放告警内存泄露
*   涉及到的函数有: 添加请在 g_checkNodeDelFuncList 中按照格式添加
*   void SLL_Delete(SLL_S *, SLL_NODE_S *)
*   void SLL_Delete_In_Middle(SLL_S *, SLL_NODE_S *, SLL_NODE_S *, SLL_NODE_S *)
*   void FECD_SLL_Delete(FECD_SLL_S *, FECD_SLL_NODE_S *)
*   void FECD_SLL_Delete_In_Middle(FECD_SLL_S *, FECD_SLL_NODE_S *, FECD_SLL_NODE_S *, FECD_SLL_NODE_S *)
*   void DLL_Delete(DLL_S *, DLL_NODE_S *)
*   void DLL_Delete_In_Middle(DLL_S *, DLL_NODE_S *, DLL_NODE_S *, DLL_NODE_S *)
*   void VASP_DLL_Delete(DLL_S *, DLL_NODE_S *)
*   VOID HASH_Delete_Node(HASH_TABLE_S *pHashTab, HASH_NODE_S  *pNode, ULONG u4HashIndex)【Example】&nbsp;&nbsp;//good example





//bad example

```
**【修复建议】**

节点从链表中删除后，需要自己释放节点的内存
