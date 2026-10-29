define([],function(){var obj={
// .......................................................................................

  /* params - {type:string, url:string}; */
  AddToMapClicked: "app/AddToMapClicked",

  /* params - {} */
  BulkUpdate: "app/BulkUpdate",

  /* params - {item:obj} */
  ItemAccessChanged: "app/ItemAccessChanged",

  /* params - {item:obj} */
  ItemApprovalStatusChanged: "app/ItemApprovalStatusChanged",

  /* params - {item:obj} */
  ItemOwnerChanged: "app/ItemOwnerChanged",

  /* params - {response:obj} */
  ItemUploaded: "app/ItemUploaded",

  /* params - {searchPane:obj,itemId:string} */
  ItemDeleted: "app/ItemDeleted",

  /* params - {item:item} */
  OnMouseEnterResultItem: "app/OnMouseEnterResultItem",
  /* params - {string:Lat,string:Lon} */
  OnGeoAddress:"app/OnGeoAddress",

  /* params - {item:item} */
  OnMouseLeaveResultItem: "app/OnMouseLeaveResultItem",

  /* params - {searchPane:obj} */
  RefreshSearchResultPage: "app/RefreshSearchResultPage",

  /* params - {collection:string} */
  CollectionChanged: "app/CollectionChanged",

  /* params - {geoportalUser:obj} */
  SignedIn: "app/SignedIn",

  /* params - {} */
  AppStarted: "app/AppStarted",

  /* params - {value:string,search:boolean} */
  SetSearchQueryFieldValue: "app/SetSearchQueryFieldValue",

  /* params - {field:string,term:string} */
  SelectSearchFilterTerm: "app/SelectSearchFilterTerm",

  /* params - {} */
  ClearAllSearchFilters: "app/ClearAllSearchFilters",

  /* params - {} */
  ShowSearchResultsView: "app/ShowSearchResultsView",

  /* params - {} */
  ShowSearchFiltersView: "app/ShowSearchFiltersView",

  /* params - {widget:obj,target:element,url:string} */
  CopyURLToClipboard: "app/CopyURLToClipboard",

  /* params - {widget:obj} */
  ClearTooltips: "app/ClearTooltips",
  
  /* params - {sort:string} */
  SortByField: "app/SortByField",

// .......................................................................................
};return obj;});
