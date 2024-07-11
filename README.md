# 【財政部電子發票整合服務平台-消費發票彙整通知】轉換Excel表格及匯入Notion程式
## 目的
爲了將格式複雜的資料集，整理出只保留重要資訊（例：消費日期、店家及金額）的Excel資料檔案。\
此外，本程式也實作匯入資料到Notion指定Database的功能，方便後續的分析。

## 產出資料集欄位
每張發票的每一個品項（明細）會佔一列資料。
1. `YM`：消費年月
2. `Invoice Number`：發票號碼
3. `Date`：消費日期
4. `Shop`：消費店家
5. `Amount`：消費金額
6. `Description`：消費品項敘述


## 測試資料集示例
以下為`test_202406.csv`產出之Excel檔。

YM	|	Invoice Number*	|	Date	|	Shop	|	Amount	|	Category
----	|	----	|	----	|	----	|	----	|	----
2024/05	|	AJ0228***4	|	8/5/2024	|	全家便利商店股份有限公司台大二活門市部	|	45	|	中熱拿鐵
2024/05	|	AJ0228***4	|	8/5/2024	|	全家便利商店股份有限公司台大二活門市部	|	34	|	星—大口義式香草烤雞飯糰 *** 鮮食促
2024/05	|	BN9288***4	|	7/5/2024	|	發發牧場股份有限公司發發港墘牧場營業所	|	85	|	鳳梨百香優格
2024/05	|	BJ9155***6	|	7/5/2024	|	哈古西式餐館	|	193	|	純手工爐烤蔬菜雞腿捲 *** 折扣金額
2024/05	|	AM0866***2	|	7/5/2024	|	萊爾富國際股份有限公司第四四七三營業處	|	86	|	香蔥腿排蛋白餐 *** 促銷折扣
2024/05	|	BL9152***2	|	6/5/2024	|	躺著喝股份有限公司江南店	|	75	|	棉被午茉綠
2024/05	|	BH7963***6	|	3/5/2024	|	蘿絲瑪莉義麵坊	|	930	|	餐費
2024/05	|	AY7300***6	|	2/5/2024	|	安心食品服務股份有限公司瑞光分公司	|	70	|	摩斯鱈魚堡
2024/05	|	AY7300***6	|	2/5/2024	|	安心食品服務股份有限公司瑞光分公司	|	99	|	T56雞塊夯地瓜

*示例中的發票號碼因資訊安全考慮予以遮罩，真實執行情況會產出完整發票號碼。

## 額外資料轉換工程
1. 去除消費金額為0的品項。
2. 移除折扣金額（消費金額為負值）的品項，將其納入同一筆發票金額最高的品項，並在此品項敘述後方注記「*** 折扣敘述」。
   - 若納入後此品項金額會變成負值，則將折扣分攤給同一筆發票其他品項，攤提比例為每個品項自身金額。

## Excel匯出功能使用方式
1. 將「財政部電子發票整合服務平台-消費發票彙整通知」檔案放入`input_folder`。
   - 可接受複數檔案。
   - 消費發票彙整通知每月會發送一次，但雙月寄送的檔案會包含單月的發票（例如：12月彙整通知會包含11月發票資訊），可以僅放入雙月資料及最新的單月資料即可。（例如：2024年2月、2024年4月、2024年6月、2024年7月）
2. 執行`export_to_excel.py`。
3. 每個檔案轉換好後會自動合并為一個Excel檔，命名規則為「Invoice_tidied_\{最早發票年月\}_\{最晚發票年月}.xlsx」（例如：`Invoice_tidied_202311_202406.xlsx`），並且會儲存在`output_folder`内。

## Notion匯入功能使用方式
1. 在Notion上新建一個Integration。
   - 前往[Integrations管理網站](https://www.notion.so/profile/integrations)。
   - 按下「New Integration」。
   - 在最上方「Add integration name」處填上自定義的名稱，且不能包含「Notion」字眼。
   - 選擇「Associated workspace」，以自身Workspace爲主。
   - 選擇「Type」，建議為「Internal」。
   - 按下「Save」。
2. 在剛建立的Integration中，複製`Internal Integration Secret`。
3. 回到Notion界面，新建一個Page之後，再用指令新增一個Database。
4. 點擊Database名稱右方的點點，按下「View Database」。
5. 提取`Database ID`。
   - 觀察瀏覽器網址處，樣式應為`https://www.notion.so/e044faa3bdc042f48ts0f69e6add4051?v=298c8e7f53714fc5a68cceba7180e11d`。
   - `Database ID`即爲`e044faa3bdc042f48ts0f69e6add4051`，在`.so/`及`?v=`中間的字串。
6. 打開Database的Integration權限。
   - 點擊最右上角的點點。
   - 點選「Connect to」。
   - 選擇剛剛新建的Integration。
   - 點選「Confirm」。
7. 複製`.env.example`，並重命名為`.env`。
8. 將`Internal Integration Secret`和`Database ID`填入對應參數。
   - NOTION_SECRET=secret_YcOpxzmf********************tiNfNNWYvNO
   - DATABASE_ID=e044faa3bdc042f48ts0f69e6add4051
9. 確保已經事先執行`export_to_excel.py`，在`output_folder`已經有`Invoice_tidied.xlsx`檔案。
   - 程式會以最近編輯日期最晚（最接近當下）的檔案爲匯入目標。
10. 執行`import_to_notion.py`。


## 錯誤排除
- 若放入非消費發票彙整通知之檔案，將會出現「Invalid file」錯誤，並顯示此檔案名稱。
- 若有更動消費發票彙整通知欄位名稱，將會出現「Invalid header」錯誤，並顯示錯誤欄位名稱。
